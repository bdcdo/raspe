"""
Scraper para o portal ANVISALegis da Agência Nacional de Vigilância Sanitária.

Este scraper usa Playwright com stealth para bypass do Cloudflare
e coleta atos normativos do portal ANVISALegis.

Exemplo:
    >>> import raspe
    >>> df = raspe.anvisa().raspar(termo="doença rara")
    >>> print(df.head())
"""

from raspe.scrapers.datalegis import ScraperDatalegis


class ScraperANVISA(ScraperDatalegis):
    """Scraper para o portal ANVISALegis.

    Coleta atos normativos da Agência Nacional de Vigilância Sanitária.

    Args:
        debug: Se True, mantém arquivos baixados.
        headless: Se True, executa em modo headless.

    Exemplo:
        >>> scraper = ScraperANVISA()
        >>> df = scraper.raspar(termo="doença rara")
        >>> print(df.columns.tolist())
        ['url', 'titulo', 'descricao', 'situacao', 'termo_busca']
    """

    _dominio = "anvisalegis.datalegis.net"
    _cod_modulo = "134"
    _cod_menu = "1696"
    _usuario = "148415"

    # Tipos de atos normativos disponíveis na ANVISA
    _sgl_tipos = (
        "ACO,ARO,ATA,ATO,AUD,AUT,ARR,AAP,BIB,ACM,COM,"
        "CTD,CPB,CRI,EXC,DSG,ETE,ETA,EXL,DCS,DEC,DLG,DEL,"
        "DLB,DEP,DIN,DPS,DST,EPP,EDT,EMC,GUI,INM,INC,LCP,"
        "LEI,ECO,CES,DOA,MSA,TCM,CON,EDL,IXL,PRG,MAN,NDT,"
        "NTA,NTC,OSV,ORT,PAR,APE,AFA,APO,CDS,CMS,CMT,CNC,"
        "CNV,DCP,DES,DIS,EQA,EXO,GRT,GDT,NOM,PEN,PRD,PRF,"
        "RQS,TTB,VAC,PLA,POR,PCJ,PIM,PNT,PSN,PAO,PTL,RLT,"
        "RES,RAM,RAU,REP,RHO,REN,RNC,RDC,TAP,EDC,TMS,VTO"
    )

    def __init__(self, debug: bool = True, headless: bool = True):
        """Inicializa o ScraperANVISA."""
        super().__init__(
            nome_buscador="ANVISA",
            debug=debug,
            headless=headless,
        )
