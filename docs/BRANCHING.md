# Branching Workflow

This project uses three branch roles:

- `master`: stable release branch.
- `dev`: integration branch for tested work before release.
- current working branch, for example `v1-fixes`: day-to-day changes.

Normal flow:

```bash
git switch v1-fixes
# make and test changes
git commit -am "Describe the fix"

git switch dev
git merge v1-fixes
# run and review the app from dev

git switch master
git merge dev
# run and review the stable app from master
```

To view a branch in the browser, switch to that branch and start the local server:

```bash
git switch dev
sample-key-indexer-web "/Users/mohammedansir/Desktop/Samples_Organised/metadata_index.json"
```

Use a different port if another branch server is already running:

```bash
sample-key-indexer-web "/Users/mohammedansir/Desktop/Samples_Organised/metadata_index.json" --port 8766
```
