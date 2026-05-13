# CGC Slab Arbitrage Scanner

Windows desktop app for scanning CGC slab arbitrage candidates.

The app uses:

- PySide6 for the GUI
- SQLite for local watchlist, scan results, and scan settings
- eBay Browse API for live active listings
- GoCollect placeholder client for future fair-value API integration
- Local CSV fallbacks for liquid-title watchlists, mock eBay listings, and fair values

## Quick Start

From PowerShell:

```powershell
cd D:\CGC_Arbitrage
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## Mock Mode

Mock mode lets you test the full scanner without eBay API access.

Create a local `.env` file from [.env.example](.env.example):

```powershell
Copy-Item .env.example .env
```

Make sure `.env` contains:

```text
CGC_EBAY_MODE=mock
```

Then run:

```powershell
.\.venv\Scripts\python.exe main.py
```

Click `Load liquid list`, then `Scan watchlist`.

## Live eBay Mode

When the eBay Developer account is active, update `.env`:

```text
CGC_EBAY_MODE=live
EBAY_CLIENT_ID=your-production-client-id
EBAY_CLIENT_SECRET=your-production-client-secret
```

The app defaults to production eBay Browse/OAuth URLs. Only set `EBAY_BROWSE_BASE_URL` and `EBAY_OAUTH_TOKEN_URL` if you are intentionally using sandbox keys.

Live scans request fixed-price listings only. Auction listings are not actionable at the current bid price, so they are excluded by default.

When eBay returns item specifics, the scanner also rejects listings marked as `Modern Age` or with a publication year after the configured cutoff. The default cutoff is 1979 for the current Silver/Bronze liquid list and can be changed with `CGC_MAX_PUBLICATION_YEAR`.

## Pricing Defaults

The default resale assumption is eBay fixed price:

- `CGC_SELLING_FEE_RATE=0.1325`
- `CGC_PAYMENT_FEE_RATE=0.00`
- `CGC_FIXED_ORDER_FEE=0.40`
- `CGC_SHIPPING_COST=18.00`

The separate payment-fee field remains available for non-eBay scenarios, but eBay managed-payment processing is treated as part of the final value fee baseline.

## GoCollect Status

GoCollect is currently a placeholder integration in [gocollect_client.py](gocollect_client.py).

Until authentication and exact endpoint mapping are confirmed, fair values come from [fair_values.csv](fair_values.csv). This is intentional: the scanner can be tested end to end without hard-coding unknown GoCollect API behavior.

## Local Data Files

- [liquid_titles.csv](liquid_titles.csv): predefined liquid CGC watchlist.
- [fair_values.csv](fair_values.csv): local fair-value lookup by title, issue, and grade.
- [mock_ebay_listings.csv](mock_ebay_listings.csv): offline eBay listings for mock scans.

SQLite data is stored at `%USERPROFILE%\.cgc_arbitrage\scanner.sqlite3` by default.

## Convention Workflow

For a buying day or convention prep checklist, use [convention_runbook.md](convention_runbook.md).

## Desktop Shortcut

The repo includes [run_app.bat](run_app.bat), which starts the app using the project virtual environment.

To create a desktop shortcut:

```powershell
cd D:\CGC_Arbitrage
.\scripts\create_desktop_shortcut.ps1
```

After that, launch the app from the `CGC Arbitrage Scanner` desktop shortcut.

## Tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp_run
```

Current coverage includes parser behavior, valuation math, mock eBay mode, local fair-value lookup, and SQLite settings persistence.
