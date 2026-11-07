# P145 multi-account portfolio target scaffold

Date: 2026-11-07
Status: complete
Merge commit: `a33443a`
PR: #861
Branch: `feature/p145-multi-account-targets`
Parent issue: #859
Task issue: #860

## Summary

The weight scan can vary existing target rows, but the live instances often have only
one target account. The Search tab now has a separate multi-account scaffold:

- choose accounts from the current run's account series;
- choose a period and weight;
- seed each target minimum from the current end value;
- edit or remove rows;
- preview the exact target YAML payload;
- use it for the next portfolio run.

`POST /api/search/portfolio` accepts a `targets` row list, validates it with the
optimizer's own target loader, writes it inside the new portfolio output directory as
`targets-scaffold.yaml`, and passes that file to the portfolio script. The live target
file is untouched.

Using the scaffold also sets the portfolio metrics and directions to the scaffolded
accounts and raises the portfolio horizon to cover the selected target period.

## Verification

- API test covers valid and invalid scaffold rows and the output path.
- Browser test adds two accounts, previews the rows, and checks metrics/directions.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`
