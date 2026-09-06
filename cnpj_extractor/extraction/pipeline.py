"""
Orquestrador do Pipeline de Ingestão (cnpj_extractor.extraction.pipeline)
========================================================================
Coordena o fluxo de extração e persistência para PostgreSQL:
- Modo Direto: Download -> Temporary ZIP -> Parser -> Postgres UPSERT.
- Modo Fila: Publicação no RabbitMQ para consumo por múltiplos workers concorrentes.
- Criação Segura de Índices: Executada de forma independente, apenas após a confirmação
  de 100% dos arquivos esperados do mês no banco de dados.
"""

from dataclasses import dataclass, field
import logging
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

from ..config import Config
from ..database import (
    DatabaseManager,
    GRUPOS_TABELAS,
    TABELAS_PERMITIDAS,
    identificar_tabela_por_arquivo,
    validar_tabela,
)
from .client import ArquivoRemoto, ReceitaFederalClient
from .parser import gerar_lotes_dados, iterar_linhas_csv
from .zip_extractor import abrir_csv_do_zip_remoto

logger = logging.getLogger("cnpj_extractor.pipeline")


@dataclass
class EstatisticasProcessamento:
    arquivos_processados: int = 0
    arquivos_ignorados: int = 0
    arquivos_com_erro: List[Tuple[str, str]] = field(default_factory=list)
    total_linhas_inseridas: int = 0
    linhas_por_tabela: Dict[str, int] = field(default_factory=dict)
    tempo_total_segundos: float = 0.0


def resolver_tabelas_solicitadas(tabelas_input: Optional[List[str]]) -> Set[str]:
    if not tabelas_input or "all" in [t.lower() for t in tabelas_input]:
        return set(GRUPOS_TABELAS["all"])

    tabelas_resolvidas: Set[str] = set()
    for item in tabelas_input:
        item_lower = item.lower().strip()
        if item_lower in GRUPOS_TABELAS:
            tabelas_resolvidas.update(GRUPOS_TABELAS[item_lower])
        elif item_lower in TABELAS_PERMITIDAS:
            tabelas_resolvidas.add(validar_tabela(item_lower))
        else:
            raise ValueError(f"Tabela ou grupo inválido: {item}")
    return tabelas_resolvidas


class IngestionPipeline:
    def __init__(
        self,
        config: Optional[Config] = None,
        db: Optional[DatabaseManager] = None,
        client: Optional[ReceitaFederalClient] = None,
    ):
        self.config = config or Config.carregar()
        self.db = db or DatabaseManager(self.config)
        self.client = client or ReceitaFederalClient(self.config)

    def executar(
        self,
        mes: Optional[str] = None,
        tabelas: Optional[List[str]] = None,
        filtro_uf: Optional[str] = None,
        limite_linhas_por_arquivo: Optional[int] = None,
        pular_ja_processados: bool = True,
        criar_indices_ao_final: bool = True,
    ) -> EstatisticasProcessamento:
        """
        Execução sequencial/direta (para testes ou container individual)
        gravando no PostgreSQL com isolamento de falhas por arquivo.
        """
        stats = EstatisticasProcessamento()
        tempo_inicio = time.time()

        # 1. Decide o mês de referência
        mes_alvo = mes or self.config.default_month
        if mes_alvo == "latest":
            print("🔍 Identificando o mês mais recente disponível na Receita Federal...")
            mes_alvo = self.client.obter_mes_mais_recente()

        print(f"📅 Mês selecionado para extração: {mes_alvo}")
        tabelas_alvo = resolver_tabelas_solicitadas(tabelas)
        print(f"📊 Tabelas a serem carregadas: {', '.join(sorted(tabelas_alvo))}")
        if filtro_uf:
            print(f"🗺️  Filtro por UF aplicado: {filtro_uf.upper()} (Estabelecimentos)")
        if limite_linhas_por_arquivo:
            print(f"⚠️  Modo de teste: limite de {limite_linhas_por_arquivo} linhas por arquivo.")

        # 2. Inicializa as tabelas no PostgreSQL
        self.db.inicializar_tabelas(list(tabelas_alvo))

        # 3. Descobre a lista de arquivos remotos
        todos_arquivos = self.client.listar_arquivos(mes_alvo)
        arquivos_para_processar: List[ArquivoRemoto] = []
        arquivos_esperados: List[str] = []

        for arq in todos_arquivos:
            tabela_correspondente = identificar_tabela_por_arquivo(arq.nome)
            if tabela_correspondente and tabela_correspondente in tabelas_alvo:
                arquivos_esperados.append(arq.nome)
                arquivos_para_processar.append(arq)

        print(f"📦 Total de arquivos selecionados: {len(arquivos_para_processar)}")

        # 4. Itera e processa cada arquivo com isolamento de erros
        for idx, arquivo in enumerate(arquivos_para_processar, 1):
            tabela = identificar_tabela_por_arquivo(arquivo.nome)
            if not tabela:
                continue

            print(f"\n[{idx}/{len(arquivos_para_processar)}] Processando {arquivo.nome} ({arquivo.tamanho_formatado}) -> Tabela: {tabela}")

            if pular_ja_processados and self.db.arquivo_ja_processado(arquivo.nome):
                print(f"  ⏭️  Arquivo '{arquivo.nome}' já processado anteriormente. Pulando...")
                stats.arquivos_ignorados += 1
                continue

            try:
                linhas_arquivo = self._processar_arquivo_stream(
                    arquivo=arquivo,
                    tabela=tabela,
                    filtro_uf=filtro_uf,
                    limite=limite_linhas_por_arquivo,
                )

                # Registra conclusão atômica no PostgreSQL
                self.db.registrar_conclusao_arquivo(
                    nome_arquivo=arquivo.nome,
                    mes=mes_alvo,
                    tabela=tabela,
                    linhas_processadas=linhas_arquivo,
                )

                stats.arquivos_processados += 1
                stats.total_linhas_inseridas += linhas_arquivo
                stats.linhas_por_tabela[tabela] = stats.linhas_por_tabela.get(tabela, 0) + linhas_arquivo

            except KeyboardInterrupt:
                print("\n🛑 Processamento interrompido manualmente pelo usuário.")
                raise
            except Exception as err:
                logger.error(f"Falha ao processar arquivo '{arquivo.nome}': {err}")
                print(f"\n  ❌ Erro ao processar '{arquivo.nome}': {err}")
                stats.arquivos_com_erro.append((arquivo.nome, str(err)))

        # 5. Verificação explícita e autônoma de conclusão antes da criação de índices
        if criar_indices_ao_final:
            self.verificar_e_criar_indices(mes=mes_alvo, tabelas=list(tabelas_alvo), arquivos_esperados=arquivos_esperados)

        stats.tempo_total_segundos = time.time() - tempo_inicio
        self._exibir_relatorio_final(stats)
        return stats

    def verificar_e_criar_indices(
        self,
        mes: Optional[str] = None,
        tabelas: Optional[List[str]] = None,
        arquivos_esperados: Optional[List[str]] = None,
    ) -> bool:
        """
        Verifica se TODOS os arquivos esperados para o mês foram processados no banco.
        Se concluído, cria/garante os índices no PostgreSQL.
        Funciona mesmo se executado separadamente após os workers finalizarem.
        """
        mes_alvo = mes or self.config.default_month
        if mes_alvo == "latest":
            mes_alvo = self.client.obter_mes_mais_recente()

        tabelas_alvo = resolver_tabelas_solicitadas(tabelas)

        if arquivos_esperados is None:
            todos_arquivos = self.client.listar_arquivos(mes_alvo)
            arquivos_esperados = [
                arq.nome for arq in todos_arquivos
                if identificar_tabela_por_arquivo(arq.nome) in tabelas_alvo
            ]

        pendentes = self.db.verificar_arquivos_pendentes(mes_alvo, arquivos_esperados)

        if pendentes:
            print(f"\n⏳ {len(pendentes)} arquivo(s) ainda pendente(s) de processamento para {mes_alvo}:")
            for p in pendentes[:5]:
                print(f"   • {p}")
            if len(pendentes) > 5:
                print(f"   ... e outros {len(pendentes) - 5} arquivos.")
            print("⚠️  A criação de índices foi postergada até a conclusão de 100% dos arquivos.")
            return False

        print(f"\n⚡ Todos os {len(arquivos_esperados)} arquivos esperados de {mes_alvo} foram confirmados no PostgreSQL!")
        print("🔨 Criando e garantindo índices de alta performance no PostgreSQL...")
        indices_criados = self.db.garantir_indices(list(tabelas_alvo))
        if indices_criados:
            print(f"✅ {len(indices_criados)} índice(s) criado(s) com sucesso: {', '.join(indices_criados)}")
        else:
            print("✅ Todos os índices recomendados já existem no PostgreSQL.")
        return True

    def _processar_arquivo_stream(
        self,
        arquivo: ArquivoRemoto,
        tabela: str,
        filtro_uf: Optional[str] = None,
        limite: Optional[int] = None,
    ) -> int:
        linhas_inseridas = 0
        tempo_inicio_arquivo = time.time()

        print(f"  📥 Baixando {arquivo.nome} em blocos para disco temporário...")
        with self.client.abrir_stream_arquivo(arquivo) as raw_http_stream:
            with abrir_csv_do_zip_remoto(raw_http_stream, encoding="latin1") as text_stream:
                print(f"  ⚙️  Processando CSV e executando UPSERT no PostgreSQL ({tabela})...")
                gerador_linhas = iterar_linhas_csv(
                    text_stream=text_stream,
                    tabela=tabela,
                    filtro_uf=filtro_uf,
                    limite=limite,
                )
                gerador_lotes = gerar_lotes_dados(
                    gerador_linhas,
                    batch_size=self.config.batch_size,
                )

                for lote in gerador_lotes:
                    qtd = self.db.inserir_lote(tabela, lote)
                    linhas_inseridas += qtd

                    delta_t = max(time.time() - tempo_inicio_arquivo, 0.001)
                    velocidade = linhas_inseridas / delta_t
                    sys.stdout.write(
                        f"\r  💾 Inseridas: {linhas_inseridas:,} linhas ({velocidade:,.0f} linhas/s)..."
                    )
                    sys.stdout.flush()

        delta_t_total = max(time.time() - tempo_inicio_arquivo, 0.001)
        velocidade_media = linhas_inseridas / delta_t_total
        print(f"\r  ✅ Concluído: {linhas_inseridas:,} linhas em {delta_t_total:.1f}s ({velocidade_media:,.0f} linhas/s)")
        return linhas_inseridas

    def _exibir_relatorio_final(self, stats: EstatisticasProcessamento) -> None:
        print("\n" + "=" * 60)
        print("🎉 RELATÓRIO DE INGESTÃO (POSTGRESQL)")
        print("=" * 60)
        print(f"📁 Banco de Dados: PostgreSQL ({self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db})")
        print(f"⏱️  Tempo Total: {stats.tempo_total_segundos:.1f} segundos")
        print(f"📄 Arquivos processados com sucesso: {stats.arquivos_processados}")
        print(f"⏭️  Arquivos ignorados (já existiam): {stats.arquivos_ignorados}")
        if stats.arquivos_com_erro:
            print(f"❌ Arquivos com falha ({len(stats.arquivos_com_erro)}):")
            for nome_arq, erro_msg in stats.arquivos_com_erro:
                print(f"   • {nome_arq}: {erro_msg}")
        print(f"🔢 Total de registros inseridos: {stats.total_linhas_inseridas:,}")
        print("-" * 60)
        print("Linhas por tabela:")
        for tab, contagem in sorted(stats.linhas_por_tabela.items()):
            print(f"  • {tab.ljust(25)}: {contagem:,} linhas")
        print("=" * 60)
