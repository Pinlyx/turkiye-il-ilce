# Contributing

Bug reports and pull requests are welcome. Wrong district at a given coordinate? Open an
issue with the coordinate, the result you got and the district you expected.

## Setup

```bash
git clone https://github.com/Pinlyx/turkiye-il-ilce
cd turkiye-il-ilce
python -m pip install -e ".[test]"
python -m pytest
```

## Ground rules

- The library stays dependency free at runtime and supports Python 3.9+.
- Tests must work offline. New lookup tests need a coordinate with a source you can name
  (landmark, official address) and the district checked against the full-resolution data.
- Do not edit `data/*` by hand. Rebuild it:

  ```bash
  python -m pip install duckdb
  python scripts/build_data.py          # newest Overture release
  python -m pytest
  ```

  Commit the regenerated files together with the new release number in `CHANGELOG.md`.
- Code is MIT, data is ODbL 1.0 (`LICENSE-DATA`). Contributions are accepted under the same terms.
