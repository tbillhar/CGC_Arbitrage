# Convention Buying Runbook

Use this checklist the day before a convention or planned buying day.

## Night Before

1. Update [fair_values.csv](fair_values.csv) for the books and grades you expect to target.
2. Confirm [liquid_titles.csv](liquid_titles.csv) contains the titles/issues you want scanned.
3. Confirm `.env` is set to the right scan mode.

For mock testing:

```text
CGC_EBAY_MODE=mock
```

For live eBay scanning:

```text
CGC_EBAY_MODE=live
EBAY_CLIENT_ID=your-production-client-id
EBAY_CLIENT_SECRET=your-production-client-secret
```

4. Launch the app from the `CGC Arbitrage Scanner` desktop shortcut.
5. Click `Load liquid list` if the watchlist is empty or has been reset.
6. Review scan settings:
   - selling fee %
   - extra payment fee %
   - fixed order fee
   - shipping cost
   - default margin %
7. Click `Scan watchlist`.
8. Review diagnostics for:
   - eBay API/configuration issues
   - listings returned
   - auction listings skipped
   - modern era/year item specifics skipped
   - missing fair values
   - unprofitable listings
9. Sort candidate listings by estimated profit and margin.
10. Spot-check the top candidates manually on eBay before relying on them.
11. Export candidates with `Export candidates CSV`.

## Buying Day

1. Bring the exported CSV or keep the app available on the laptop.
2. Use `Max Buy` as the ceiling, not the target offer.
3. Re-check current market values before making large purchases.
4. Adjust scan settings if shipping, fees, or target margin assumptions change.
5. Avoid buying books where the app skipped value lookup or where the grade/page quality is uncertain.

## After Buying

1. Update local fair values if market assumptions changed.
2. Add promising new liquid titles to [liquid_titles.csv](liquid_titles.csv).
3. Add new grade/value rows to [fair_values.csv](fair_values.csv).
4. Commit and push any CSV improvements that should be preserved.
