from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TA35Company:
    """Static snapshot of TA-35-style large-cap Israeli names (Yahoo `.TA` symbols).

    Official index membership changes; refresh symbols from TASE when in doubt.
    """

    symbol: str
    name_he: str
    name_en: str
    sector_he: str
    category_he: str


# 35 liquid `.TA` names validated via Yahoo history in this environment (May 2026).
# Not guaranteed to match the exchange's official TA-35 list on every rebalance.
TA35_COMPANIES: tuple[TA35Company, ...] = (
    TA35Company("TEVA.TA", "טבע", "Teva Pharmaceutical", "תרופות", "צמיחה/ערך"),
    TA35Company("LUMI.TA", "לאומי", "Bank Leumi", "בנקאות", "מוסדי/דיבידנד"),
    TA35Company("POLI.TA", "הפועלים", "Bank Hapoalim", "בנקאות", "מוסדי/דיבידנד"),
    TA35Company("MZTF.TA", "מזרחי טפחות", "Mizrahi Tefahot", "בנקאות", "מוסדי/דיבידנד"),
    TA35Company("DSCT.TA", "דיסקונט", "Israel Discount Bank", "בנקאות", "מוסדי/דיבידנד"),
    TA35Company("FIBI.TA", "הבינלאומי הראשון", "First International Bank", "בנקאות", "מוסדי/דיבידנד"),
    TA35Company("BEZQ.TA", "בזק", "Bezeq", "תקשורת", "תשתיות/שירותים"),
    TA35Company("NICE.TA", "נייס", "NICE", "תוכנה/טכנולוגיה", "צמיחה בינלאומית"),
    TA35Company("ESLT.TA", "אלביט מערכות", "Elbit Systems", "בטחון/אירו", "בטחון"),
    TA35Company("TSEM.TA", "טאואר סמיקונדקטור", "Tower Semiconductor", "מוליכים למחצה", "מחזור עסקי"),
    TA35Company("ORA.TA", "אורמת", "Ormat", "אנרגיה", "אנרגיה/תשתיות"),
    TA35Company("ICL.TA", "כימיקלים לישראל", "ICL", "כימיקלים", "סחורות/מחזור"),
    TA35Company("CAMT.TA", "קמטק", "Camtek", "ציוד לבדיקות", "טכנולוגיה"),
    TA35Company("AZRG.TA", "קבוצת עזריאלי", "Azrieli Group", "נדל\"ן", "נדל\"ן מניב"),
    TA35Company("PHOE.TA", "פניקס", "Phoenix Holdings", "ביטוח", "פיננסים"),
    TA35Company("HARL.TA", "הראל השקעות", "Harel", "ביטוח", "פיננסים"),
    TA35Company("MGDL.TA", "מגדל ביטוח", "Migdal Insurance", "ביטוח", "פיננסים"),
    TA35Company("CLIS.TA", "כלל ביטוח", "Clal Insurance", "ביטוח", "פיננסים"),
    TA35Company("STRS.TA", "שטראוס", "Strauss", "מזון", "מותגים/צריכה"),
    TA35Company("SAE.TA", "שופרסל", "Shufersal", "קמעונאות", "צריכה פנימית"),
    TA35Company("BIG.TA", "ביג", "BIG Shopping Centers", "נדל\"ן", "קמעונאות/מניב"),
    TA35Company("AMOT.TA", "אמות", "Amot Investments", "נדל\"ן", "מניב"),
    TA35Company("DLEKG.TA", "דלק קבוצה", "Delek Group", "אנרגיה", "אנרגיה"),
    TA35Company("MMHD.TA", "מנורה מבטחים", "Menora Mivtachim", "ביטוח", "פיננסים"),
    TA35Company("FTAL.TA", "פטאל", "Fattal", "אירוח/תיירות", "ציקלי"),
    TA35Company("NVPT.TA", "נובולוג", "Novolog", "לוגיסטיקה", "תשתיות"),
    TA35Company("CEL.TA", "סלקום", "Cellcom", "תקשורת", "תחרותית"),
    TA35Company("ALHE.TA", "אל על", "El Al", "תחבורה", "ציקלי"),
    TA35Company("ENLT.TA", "אנלייט אנרגיה", "Enlight Renewable Energy", "אנרגיה מתחדשת", "אנרגיה"),
    TA35Company("HLAN.TA", "הילן", "Hilan", "שירותי כ\"א", "שירותים"),
    TA35Company("ISRS.TA", "ישראמקו", "Israel Corp", "אחזקות", "חברת אחזקות"),
    TA35Company("MLSR.TA", "מליסרון", "Melisron", "נדל\"ן", "מניב"),
    TA35Company("PERI.TA", "פריורטק", "Perion", "דיגיטל/מדיה", "טכנולוגיה"),
    TA35Company("MTRX.TA", "מטריקס", "Matrix", "IT שירותים", "טכנולוגיה"),
    TA35Company("ROTS.TA", "רוטשטיין", "Rothschild", "השקעות", "פיננסים"),
)


def ta35_symbols() -> tuple[str, ...]:
    return tuple(c.symbol for c in TA35_COMPANIES)


def company_by_symbol(symbol: str) -> TA35Company | None:
    for c in TA35_COMPANIES:
        if c.symbol == symbol:
            return c
    return None


def knowledge_catalog_digest() -> str:
    lines = ["מאגר ידע TA-35 (קטגוריות בסיסיות):", ""]
    for c in TA35_COMPANIES:
        lines.append(f"- {c.symbol}: {c.name_he} | מגזר: {c.sector_he} | קטגוריה: {c.category_he}")
    return "\n".join(lines)
