"""
Scraper para o portal ANSLegis da Agência Nacional de Saúde Suplementar.

Este scraper usa Playwright com stealth para bypass do Cloudflare
e coleta atos normativos do portal ANSLegis.

Exemplo:
    >>> import raspe
    >>> df = raspe.ans().raspar(termo="doença rara")
    >>> print(df.head())
"""

from raspe.scrapers.datalegis import ScraperDatalegis


class ScraperANS(ScraperDatalegis):
    """Scraper para o portal ANSLegis.

    Coleta atos normativos da Agência Nacional de Saúde Suplementar.

    Args:
        debug: Se True, mantém arquivos baixados.
        headless: Se True, executa em modo headless.

    Exemplo:
        >>> scraper = ScraperANS()
        >>> df = scraper.raspar(termo="doença rara")
        >>> print(df.columns.tolist())
        ['url', 'titulo', 'descricao', 'situacao', 'termo_busca']
    """

    _dominio = "anslegis.datalegis.net"
    _cod_modulo = "583"  # LEGISLAÇÃO ESTRUTURANTE (público)
    _cod_menu = "8431"

    # Tipos de atos normativos disponíveis na ANS
    _sgl_tipos = (
        ",DEC,DLG,DEL,LCP,LEI,CON,DLB,DEP,DPS,ITR,"
        ",INM,INC,ISV,NED,NTC,OFC,ORT,POR,PCJ,PIM,PNT,PDP,"
        "RES,RAM,RSC,RHO,REN,ROP,ARO,ATO,AUD,BIB,ACM,COM,"
        "CPB,EXC,ETE,ETA,EXL,DCS,EXD,EDT,EXM,ISC,ECO,CES,"
        "COV,EXS,EIT,MSA,TCM,COR,EDL,IXL,PRG,ERP,MAN,AFU,"
        "APE,ITM,AFA,APO,APT,ADR,CMS,CNC,DCP,DES,DIS,EXO,"
        "GRT,GDT,LIC,NOM,PEN,REC,RQS,RSO,REV,VAC,PDS,RCO,"
        "REP,RNC,RGM,RDC,TMS,VTO,ACO,PAO"
    )

    def __init__(self, debug: bool = True, headless: bool = True):
        """Inicializa o ScraperANS."""
        super().__init__(
            nome_buscador="ANS",
            debug=debug,
            headless=headless,
        )
