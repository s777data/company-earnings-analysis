window.EARNINGS_REPORT = {
  "schema_version": 2,
  "company": {
    "ticker": "RKLB",
    "period": "Q2 FY2026",
    "report_date": "2026-06-30",
    "call_date": "2026-08-10",
    "grade": "A",
    "confidence": 0.9500000000000001,
    "recommendation": "INSUFFICIENT DATA",
    "price": 80.25,
    "market_cap": 48005661698.75607,
    "pe_ttm": -287.02,
    "high_52": 150.9999,
    "low_52": 37.57,
    "test_run": true
  },
  "sections": {
    "income_statement": [
      {
        "key": "revenue",
        "name": "Revenue",
        "raw_value": 234066000.0,
        "display_value": "$234.1M",
        "comparison": "+62.0% YoY",
        "status": "best",
        "tier": "best",
        "assessment": "+62.0% YoY",
        "description": "Revenue recognized during the reported period.",
        "why_it_matters": "Shows the scale and growth of the core business.",
        "directionality": "Higher is generally better when growth is profitable.",
        "formula": "Reported revenue for the period",
        "scale": [
          {
            "label": "Declining",
            "max": 0,
            "signal": "negative"
          },
          {
            "label": "Stable",
            "max": 0.1,
            "signal": "neutral"
          },
          {
            "label": "Strong growth",
            "max": null,
            "signal": "positive"
          }
        ],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "gross_profit",
        "name": "Gross Profit",
        "raw_value": 84576000.0,
        "display_value": "$84.6M",
        "comparison": "+82.3% YoY",
        "status": "best",
        "tier": "best",
        "assessment": "+82.3% YoY",
        "description": "Revenue remaining after direct costs.",
        "why_it_matters": "Funds operating expenses, investment, and profit.",
        "directionality": "Higher and expanding is generally better.",
        "formula": "Revenue − cost of revenue",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "operating_income",
        "name": "Operating Income",
        "raw_value": -57514000.0,
        "display_value": "-$57.5M",
        "comparison": "+3.6% YoY",
        "status": "neutral",
        "tier": "neutral",
        "assessment": "+3.6% YoY",
        "description": "Profit from core operations before interest and taxes.",
        "why_it_matters": "Measures operating execution and cost discipline.",
        "directionality": "Higher is generally better.",
        "formula": "Gross profit − operating expenses",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "net_income",
        "name": "Net Income",
        "raw_value": -49258000.0,
        "display_value": "-$49.3M",
        "comparison": "+25.8% YoY",
        "status": "strong_positive",
        "tier": "strong_positive",
        "assessment": "+25.8% YoY",
        "description": "Profit attributable after all recognized expenses.",
        "why_it_matters": "Captures the period's bottom-line result.",
        "directionality": "Higher and durable is generally better.",
        "formula": "Revenue − all expenses, interest, and tax",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      }
    ],
    "key_ratios": [
      {
        "key": "gross_margin",
        "name": "Gross Margin",
        "raw_value": 0.36133398272282174,
        "display_value": "36.1%",
        "comparison": "current quarter",
        "status": "best",
        "tier": "best",
        "assessment": "current quarter",
        "description": "Share of revenue remaining after direct costs.",
        "why_it_matters": "Shows product economics and pricing/cost performance.",
        "directionality": "Higher and durable is generally better.",
        "formula": "Gross profit ÷ revenue",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "operating_margin",
        "name": "Operating Margin",
        "raw_value": -0.24571701998581597,
        "display_value": "-24.6%",
        "comparison": "current quarter",
        "status": "worst",
        "tier": "worst",
        "assessment": "current quarter",
        "description": "Share of revenue retained as operating profit.",
        "why_it_matters": "Measures operating efficiency and pricing power.",
        "directionality": "Higher and durable is generally better.",
        "formula": "Operating income ÷ revenue",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "net_margin",
        "name": "Net Margin",
        "raw_value": -0.21044491724556322,
        "display_value": "-21.0%",
        "comparison": "current quarter",
        "status": "worst",
        "tier": "worst",
        "assessment": "current quarter",
        "description": "Share of revenue retained as net income.",
        "why_it_matters": "Summarizes bottom-line profitability.",
        "directionality": "Higher and durable is generally better.",
        "formula": "Net income ÷ revenue",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "revenue_growth",
        "name": "Revenue Growth",
        "raw_value": null,
        "display_value": "+62.0%",
        "comparison": "year over year",
        "status": "best",
        "tier": "best",
        "assessment": "year over year",
        "description": "A verified company-reported financial measure.",
        "why_it_matters": "Provides context for operating performance, financial position, or valuation.",
        "directionality": "Interpret with the company's trend, peers, and business model.",
        "formula": "See the cited source and calculation context.",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "operating_income_growth",
        "name": "Operating Income Growth",
        "raw_value": null,
        "display_value": "+3.6%",
        "comparison": "year over year",
        "status": "neutral",
        "tier": "neutral",
        "assessment": "year over year",
        "description": "A verified company-reported financial measure.",
        "why_it_matters": "Provides context for operating performance, financial position, or valuation.",
        "directionality": "Interpret with the company's trend, peers, and business model.",
        "formula": "See the cited source and calculation context.",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      },
      {
        "key": "net_income_growth",
        "name": "Net Income Growth",
        "raw_value": null,
        "display_value": "+25.8%",
        "comparison": "year over year",
        "status": "strong_positive",
        "tier": "strong_positive",
        "assessment": "year over year",
        "description": "A verified company-reported financial measure.",
        "why_it_matters": "Provides context for operating performance, financial position, or valuation.",
        "directionality": "Interpret with the company's trend, peers, and business model.",
        "formula": "See the cited source and calculation context.",
        "scale": [],
        "source_note": "SEC XBRL",
        "source_date": null
      }
    ],
    "valuation": [
      {
        "key": "ps_annualized",
        "name": "P/S (Annualized)",
        "raw_value": 51.13316258869033,
        "display_value": "51.1x",
        "comparison": "Very Expensive",
        "status": "worst",
        "tier": 1,
        "assessment": "Very Expensive",
        "description": "Market capitalization / annualized revenue.",
        "why_it_matters": "Shows how much equity investors are paying for each dollar of annualized sales. Useful when earnings are negative or too small for P/E to be meaningful.",
        "directionality": "Lower is better",
        "formula": "Market cap ÷ annualized revenue",
        "scale": [
          {
            "max": 2,
            "label": "Attractive",
            "signal": "positive"
          },
          {
            "max": 5,
            "label": "Moderate",
            "signal": "neutral"
          },
          {
            "max": 10,
            "label": "Expensive",
            "signal": "caution"
          },
          {
            "max": null,
            "label": "Very Expensive",
            "signal": "worst"
          }
        ],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "ev_revenue",
        "name": "EV / Revenue",
        "raw_value": 48.87892899177369,
        "display_value": "48.9x",
        "comparison": "Expensive",
        "status": "negative",
        "tier": 1,
        "assessment": "Expensive",
        "description": "Enterprise value / total annualized revenue.",
        "why_it_matters": "Tells you how much you are paying for one dollar of total sales, adjusting for debt and cash.",
        "directionality": "Lower is better",
        "formula": "Enterprise value ÷ annualized revenue",
        "scale": [
          {
            "max": 2,
            "label": "Deep Value",
            "signal": "positive"
          },
          {
            "max": 5,
            "label": "Typical",
            "signal": "neutral"
          },
          {
            "max": null,
            "label": "Expensive",
            "signal": "negative"
          }
        ],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "ev_gross_profit",
        "name": "EV / Gross Profit",
        "raw_value": 135.27354560854732,
        "display_value": "135.3x",
        "comparison": "Context Only",
        "status": "neutral",
        "tier": 2,
        "assessment": "Context Only",
        "description": "Enterprise value / annualized gross profit.",
        "why_it_matters": "Shows whether the core product is profitable to make before corporate overhead and management costs.",
        "directionality": "Lower is better",
        "formula": "Enterprise value ÷ annualized gross profit",
        "scale": [],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "ev_revenue_growth",
        "name": "EV / Revenue / Growth",
        "raw_value": 0.7885525501801217,
        "display_value": "0.8x",
        "comparison": "Context Only",
        "status": "neutral",
        "tier": 2,
        "assessment": "Context Only",
        "description": "(EV / Revenue) / YoY Revenue Growth Rate (%).",
        "why_it_matters": "Factors sales growth into the revenue multiple, functioning like a PEG ratio for top-line sales.",
        "directionality": "Lower is better",
        "formula": "EV/Revenue ÷ YoY revenue growth %",
        "scale": [],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "price_to_book",
        "name": "Price to Book (P/B)",
        "raw_value": 13.74672349658107,
        "display_value": "13.7x",
        "comparison": "Expensive",
        "status": "negative",
        "tier": 2,
        "assessment": "Expensive",
        "description": "Market cap / total equity (or tangible book value).",
        "why_it_matters": "Shows the price paid relative to the accounting value of assets after liabilities.",
        "directionality": "Lower is better",
        "formula": "Market cap ÷ total equity",
        "scale": [
          {
            "max": 1,
            "label": "Below Book",
            "signal": "positive"
          },
          {
            "max": 3,
            "label": "Typical",
            "signal": "neutral"
          },
          {
            "max": null,
            "label": "Expensive",
            "signal": "negative"
          }
        ],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "ev_backlog",
        "name": "EV / Backlog",
        "raw_value": 19.478055636499803,
        "display_value": "19.5x",
        "comparison": "Context Only",
        "status": "neutral",
        "tier": 1,
        "assessment": "Context Only",
        "description": "Enterprise value / total order backlog.",
        "why_it_matters": "Compares enterprise value with contracted future work for project-based companies.",
        "directionality": "Lower is better",
        "formula": "Enterprise value ÷ reported backlog",
        "scale": [],
        "source_note": "robinhood-trading MCP completed daily regular-session close; SEC filing/XBRL",
        "source_date": null
      }
    ],
    "valuation_regime": "Negative Earnings / FCF",
    "short_interest_sbc": [
      {
        "key": "short_interest_float",
        "name": "Short Interest % of Float",
        "raw_value": 7.773659126344186,
        "display_value": "7.8%",
        "comparison": "Moderate",
        "status": "neutral",
        "tier": 1,
        "assessment": "Moderate",
        "description": "Shares sold short / public float.",
        "why_it_matters": "Shows bearish positioning and potential short-squeeze pressure.",
        "directionality": "Lower is generally safer",
        "formula": "Shares sold short ÷ public float",
        "scale": [
          {
            "max": 5,
            "label": "Low",
            "signal": "positive"
          },
          {
            "max": 10,
            "label": "Moderate",
            "signal": "neutral"
          },
          {
            "max": 20,
            "label": "High",
            "signal": "caution"
          },
          {
            "max": null,
            "label": "Very High",
            "signal": "worst"
          }
        ],
        "source_note": "Nasdaq official short-interest report",
        "source_date": "07/31/2026"
      },
      {
        "key": "days_to_cover",
        "name": "Short Ratio / Days to Cover",
        "raw_value": 2.418186,
        "display_value": "2.4d",
        "comparison": "Moderate",
        "status": "neutral",
        "tier": 1,
        "assessment": "Moderate",
        "description": "Shares sold short / average daily trading volume.",
        "why_it_matters": "Estimates how many normal trading days shorts would need to cover their positions.",
        "directionality": "Lower is generally safer",
        "formula": "Shares sold short ÷ average daily volume",
        "scale": [
          {
            "max": 2,
            "label": "Low",
            "signal": "positive"
          },
          {
            "max": 5,
            "label": "Moderate",
            "signal": "neutral"
          },
          {
            "max": 10,
            "label": "High",
            "signal": "caution"
          },
          {
            "max": null,
            "label": "Very High",
            "signal": "worst"
          }
        ],
        "source_note": "Nasdaq official short-interest report",
        "source_date": "07/31/2026"
      },
      {
        "key": "sbc_revenue",
        "name": "SBC / Revenue",
        "raw_value": 8.357044594259738,
        "display_value": "8.4%",
        "comparison": "Moderate",
        "status": "neutral",
        "tier": 1,
        "assessment": "Moderate",
        "description": "Stock-based compensation expense / revenue.",
        "why_it_matters": "Shows how much revenue is consumed by recurring equity compensation.",
        "directionality": "Lower is better",
        "formula": "Stock-based compensation ÷ revenue",
        "scale": [
          {
            "max": 5,
            "label": "Low",
            "signal": "positive"
          },
          {
            "max": 10,
            "label": "Moderate",
            "signal": "neutral"
          },
          {
            "max": 20,
            "label": "High",
            "signal": "caution"
          },
          {
            "max": null,
            "label": "Very High",
            "signal": "worst"
          }
        ],
        "source_note": "SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "sbc_adjusted_fcf_yield",
        "name": "SBC-Adjusted FCF Yield",
        "raw_value": -0.7926095607616807,
        "display_value": "-0.8%",
        "comparison": "Very Expensive",
        "status": "worst",
        "tier": 1,
        "assessment": "Very Expensive",
        "description": "(Levered FCF - stock-based compensation) / market capitalization.",
        "why_it_matters": "Measures shareholder cash yield after treating SBC as an economic cost.",
        "directionality": "Higher is better",
        "formula": "(Levered FCF − SBC) ÷ market cap",
        "scale": [
          {
            "max": 2,
            "label": "Very Expensive",
            "signal": "worst"
          },
          {
            "max": 4,
            "label": "Expensive",
            "signal": "negative"
          },
          {
            "max": 8,
            "label": "Reasonable",
            "signal": "neutral"
          },
          {
            "max": null,
            "label": "Attractive",
            "signal": "positive"
          }
        ],
        "source_note": "SEC filing/XBRL",
        "source_date": null
      },
      {
        "key": "net_share_dilution",
        "name": "Net Share Dilution",
        "raw_value": 22.247747292047258,
        "display_value": "22.2%",
        "comparison": "Very High",
        "status": "worst",
        "tier": 1,
        "assessment": "Very High",
        "description": "Percentage change in diluted shares outstanding over the period.",
        "why_it_matters": "Shows whether issuance and SBC dilute existing shareholders after buybacks.",
        "directionality": "Lower is better",
        "formula": "Change in diluted weighted-average shares",
        "scale": [
          {
            "max": 0,
            "label": "Shrinking",
            "signal": "positive"
          },
          {
            "max": 1,
            "label": "Minimal",
            "signal": "positive"
          },
          {
            "max": 3,
            "label": "Moderate",
            "signal": "neutral"
          },
          {
            "max": 5,
            "label": "High",
            "signal": "caution"
          },
          {
            "max": null,
            "label": "Very High",
            "signal": "worst"
          }
        ],
        "source_note": "SEC filing/XBRL",
        "source_date": null
      }
    ],
    "capital_liquidity": [
      {
        "name": "Capital Expenditures",
        "value": "$15.4M",
        "signal": "positive",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "CapitalExpendituresIncurredButNotYetPaid",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-1",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": "2026-01-01",
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Total Assets",
        "value": "$4.19B",
        "signal": "neutral",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "Assets",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-3",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": null,
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Total Equity",
        "value": "$3.49B",
        "signal": "best",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "StockholdersEquity",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-3",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": null,
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Operating Cash Flow",
        "value": "-$134.4M",
        "signal": "worst",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "NetCashProvidedByUsedInOperatingActivities",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-1",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": "2026-01-01",
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Total Liabilities",
        "value": "$695.2M",
        "signal": "neutral",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "Liabilities",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-3",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": null,
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Cash",
        "value": "$2.13B",
        "signal": "neutral",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "CashAndCashEquivalentsAtCarryingValue",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-3",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": null,
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Long-term Debt",
        "value": "$13.1M",
        "signal": "neutral",
        "citation": {
          "source": "SEC XBRL",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
          "start": null,
          "end": null,
          "concept": "LongTermDebt",
          "taxonomy": "http://fasb.org/us-gaap/2026",
          "context": "c-3",
          "dimensions": [],
          "unit": "usd",
          "decimals": "-3",
          "period_start": null,
          "period_end": "2026-06-30"
        }
      },
      {
        "name": "Net cash / (debt)",
        "value": "$2.12B",
        "signal": "positive",
        "citation": [
          {
            "source": "SEC XBRL",
            "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
            "start": null,
            "end": null,
            "concept": "CashAndCashEquivalentsAtCarryingValue",
            "taxonomy": "http://fasb.org/us-gaap/2026",
            "context": "c-3",
            "dimensions": [],
            "unit": "usd",
            "decimals": "-3",
            "period_start": null,
            "period_end": "2026-06-30"
          },
          {
            "source": "SEC XBRL",
            "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
            "start": null,
            "end": null,
            "concept": "LongTermDebt",
            "taxonomy": "http://fasb.org/us-gaap/2026",
            "context": "c-3",
            "dimensions": [],
            "unit": "usd",
            "decimals": "-3",
            "period_start": null,
            "period_end": "2026-06-30"
          }
        ]
      }
    ],
    "guidance": [
      {
        "name": "Forward outlook",
        "detail": "We expect revenue in the second quarter to range between $250 million and $265 million, representing 10% quarter-over-quarter revenue growth at the midpoint.",
        "signal": "positive",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 25920,
          "end": 26077
        }
      },
      {
        "name": "Forward outlook",
        "detail": "Second quarter 2026 revenue was a record $234 million, which was within our prior guidance range and reflects significant year-over-year growth of 62% and 16.8% sequentially, driven by strong contribution from both business segments.",
        "signal": "best",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 18717,
          "end": 18950
        }
      },
      {
        "name": "Forward outlook",
        "detail": "Non-GAAP gross margin for the second quarter was 41.5%, which was also above our prior guidance range of 38%-40%.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 20201,
          "end": 20314
        }
      },
      {
        "name": "Forward outlook",
        "detail": "We anticipate GAAP gross margin to range between 29%-31% and non-GAAP gross margin to range between 35%-37%.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 26078,
          "end": 26186
        }
      },
      {
        "name": "Forward outlook",
        "detail": "GAAP gross margin for the second quarter was 36.1%, above our prior guidance range of 33%-35%.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 20106,
          "end": 20200
        }
      },
      {
        "name": "Forward outlook",
        "detail": "We expect third quarter GAAP operating expenses to range between $143 million and $149 million, and non-GAAP operating expenses to range between $121 million and $127 million.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 26387,
          "end": 26562
        }
      }
    ],
    "earnings_call": [
      {
        "topic": "Management Tone",
        "category": "outlook",
        "detail": "We expect this momentum to continue, guiding to strong revenue growth as our satellite platforms business scales exceptionally and Neutron progresses towards first flight.",
        "signal": "best",
        "tier": "best",
        "reasoning": "The cited prepared remarks evidence is supportive for management tone.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 27708,
          "end": 27879
        },
        "confidence_category": "Confident",
        "confidence_subcategory": "Assured",
        "confidence_rank": 4,
        "confidence_reasoning": "Aggregate management-language scores were Confident 118, Vague 17, and Not Confident 14; the leading assured cues were we expect (10), we anticipate (1), confidence (2)."
      },
      {
        "topic": "Revenue & Demand",
        "category": "revenue",
        "detail": "While bookings across Space Systems and launch can be inherently lumpy due to the timing of increasingly larger, high-impact program opportunities, backlog continues to hold at healthy levels despite the step-up in revenue run rate recognition over the past few quarters.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "The cited prepared remarks evidence is mixed or monitoring for revenue & demand.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 21145,
          "end": 21416
        }
      },
      {
        "topic": "Margins & Profitability",
        "category": "margin",
        "detail": "These forecasted GAAP and non-GAAP gross margins are accounting for a shift in mix within our Space Systems business, and we expect a beneficial remixing impact on gross margins as we look beyond Q3.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "The cited prepared remarks evidence is mixed or monitoring for margins & profitability.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 26187,
          "end": 26386
        }
      },
      {
        "topic": "Guidance",
        "category": "guidance",
        "detail": "We expect revenue in the second quarter to range between $250 million and $265 million, representing 10% quarter-over-quarter revenue growth at the midpoint.",
        "signal": "positive",
        "tier": "positive",
        "reasoning": "The cited prepared remarks evidence is supportive for guidance.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 25920,
          "end": 26077
        }
      },
      {
        "topic": "Products & Innovation",
        "category": "product",
        "detail": "Our focus is on the bigger picture and making sure that when Neutron flies, it enters service as a system ready for full-scale production and high cadence launch.",
        "signal": "positive",
        "tier": "positive",
        "reasoning": "The cited prepared remarks evidence is supportive for products & innovation.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 14146,
          "end": 14308
        }
      },
      {
        "topic": "Customers & Engagement",
        "category": "customer",
        "detail": "In short, Rocket Lab will become a self-launching tier 1 space power, delivering critical communications capability to millions of users worldwide.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "The cited prepared remarks evidence is mixed or monitoring for customers & engagement.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 4277,
          "end": 4424
        }
      },
      {
        "topic": "Capital Allocation",
        "category": "capital",
        "detail": "As we progress towards Neutron's first flight, we expect capital expenditures to remain elevated as we invest in testing, production scaling, and infrastructure expansion.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "The cited prepared remarks evidence is mixed or monitoring for capital allocation.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 23594,
          "end": 23765
        }
      },
      {
        "topic": "Competition & Market",
        "category": "competition",
        "detail": "Again, another strong signal of the expectation for Neutron to become the industry's alternate ride to space for medium-lift missions.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "The cited prepared remarks evidence is mixed or monitoring for competition & market.",
        "section": "Prepared Remarks",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 17552,
          "end": 17686
        }
      },
      {
        "topic": "Analyst Q&A",
        "category": "qa",
        "detail": "Clearly, you've seen the strain in the launch industry right now and the need, not just for new vehicles, but new vehicles at cadence.",
        "signal": "neutral",
        "tier": "neutral",
        "reasoning": "This is a substantive management response from the analyst Q&A section.",
        "section": "Analyst Q&A",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 30562,
          "end": 30696
        }
      }
    ],
    "channels": [
      {
        "name": "Products & platforms",
        "desc": "Our focus is on the bigger picture and making sure that when Neutron flies, it enters service as a system ready for full-scale production and high cadence launch.",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 14146,
          "end": 14308
        }
      },
      {
        "name": "Customers & engagement",
        "desc": "In short, Rocket Lab will become a self-launching tier 1 space power, delivering critical communications capability to millions of users worldwide.",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 4277,
          "end": 4424
        }
      },
      {
        "name": "Markets & distribution",
        "desc": "A growing presence there also represents an opportunity to address Europe's launch deficit by bringing a domestic mission-tested launch partner to the region to eliminate space access bottlenecks.",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 10305,
          "end": 10501
        }
      },
      {
        "name": "Business lines",
        "desc": "Meanwhile, our Launch Services segment generated revenue of $44.6 million this quarter, representing a 30% decrease compared to the previous quarter, despite completing a similar number of launches.",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 19423,
          "end": 19621
        }
      }
    ],
    "strategic_pillars": [
      {
        "name": "Innovation Roadmap",
        "detail": "Our two new pads in Alaska will be deployed using our GHOST containerized deployable launch site technology.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 12432,
          "end": 12540
        }
      },
      {
        "name": "Growth Expansion",
        "detail": "That mission will expand the capacity of their network with on-orbit compute, optical comms, and hosted payloads.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 17335,
          "end": 17448
        }
      },
      {
        "name": "Customer Value",
        "detail": "Across Launch Services and Space Systems, we have signed more than $1 billion in new contracts across Q2 and the period since the quarter closed.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 3580,
          "end": 3725
        }
      },
      {
        "name": "Operational Excellence",
        "detail": "We continue to see a strong pipeline that includes multi-launch agreements and large satellite manufacturing contracts across government and commercial programs.",
        "signal": "positive",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 21417,
          "end": 21578
        }
      },
      {
        "name": "Capital Discipline",
        "detail": "Lastly, consistent with prior quarters, we expect negative non-GAAP free cash flow in the third quarter to remain at elevated levels, driven by ongoing investments in Neutron development and scaling production.",
        "signal": "neutral",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 27207,
          "end": 27417
        }
      },
      {
        "name": "Long-Term Strategy",
        "detail": "It was also a milestone quarter for strategic acquisitions, having closed Mynaric and Motiv, and of course, announcing our intentions to acquire Iridium, which will accelerate our future in-space applications and evolve Rocket Lab into a fully integrated space powerhouse.",
        "signal": "positive",
        "citation": {
          "source": "earnings call transcript",
          "url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
          "start": 3726,
          "end": 3998
        }
      }
    ],
    "risks": [
      {
        "risk": "Regulatory / legal exposure",
        "evidence": "The Company is, and from time to time may be, a party to claims and legal proceedings generally incidental to its business that are principally covered under contracts with its customers and insurance policies.",
        "probability": null,
        "eps_impact": null,
        "quantification": "Not company-disclosed; no probability or EPS impact invented",
        "signal": "caution",
        "citation": {
          "source": "SEC filing / earnings transcript",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm",
          "start": 123883,
          "end": 124093
        }
      },
      {
        "risk": "Demand / macro exposure",
        "evidence": "In addition, we are subject to broader market risk that is created by the global market disruptions and uncertainties resulting from macroeconomic challenges, geopolitical events, tariffs, trade and other international disputes.",
        "probability": null,
        "eps_impact": null,
        "quantification": "Not company-disclosed; no probability or EPS impact invented",
        "signal": "negative",
        "citation": {
          "source": "SEC filing / earnings transcript",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm",
          "start": 181657,
          "end": 181886
        }
      },
      {
        "risk": "Capital intensity / cash-flow pressure",
        "evidence": "Additional delays or setbacks in Neutron development may require more research, development and capital expenditures than we currently anticipate, which could adversely affect our liquidity and capital resources in future periods.",
        "probability": null,
        "eps_impact": null,
        "quantification": "Not company-disclosed; no probability or EPS impact invented",
        "signal": "caution",
        "citation": {
          "source": "SEC filing / earnings transcript",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm",
          "start": 142666,
          "end": 142897
        }
      },
      {
        "risk": "Supply / execution exposure",
        "evidence": "This delay is the result of a number of factors, including delays that have arisen in the Company’s supply chain.",
        "probability": null,
        "eps_impact": null,
        "quantification": "Not company-disclosed; no probability or EPS impact invented",
        "signal": "caution",
        "citation": {
          "source": "SEC filing / earnings transcript",
          "url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm",
          "start": 68998,
          "end": 69112
        }
      }
    ],
    "thesis": {
      "recommendation": "INSUFFICIENT DATA",
      "hurdle_rate": 0.12,
      "scenario_weights": {
        "base_case": 0.5,
        "bull_case": 0.3,
        "bear_case": 0.2
      },
      "method": "Five-year EPS scenarios use broker-derived TTM EPS, bounded reported growth, and transparent scenario weights/multiples.",
      "key_risks_summary": "Regulatory / legal exposure, Demand / macro exposure, Capital intensity / cash-flow pressure"
    }
  },
  "sources": {
    "filing_url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm",
    "xbrl_url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630_htm.xml",
    "earnings_release_url": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000061/rklb-20260810.htm",
    "transcript_url": "https://stockanalysis.com/stocks/rklb/transcripts/662835-q2-2026/",
    "transcript_provider": "stockanalysis.com",
    "transcript_call_date": "2026-08-10",
    "transcript_retrieved_at": "2026-08-15T05:30:34.453774+00:00",
    "transcript_content_sha256": "cabdbbe7cbaba58b111e49da3d098891e8e4b270ad671fbecdb3c6143bf561d4",
    "short_interest_url": "https://www.nasdaq.com/market-activity/stocks/rklb/short-interest"
  },
  "warnings": [
    "TEST ONLY — stale Robinhood market data explicitly allowed; valuation and recommendation are not actionable"
  ]
};
