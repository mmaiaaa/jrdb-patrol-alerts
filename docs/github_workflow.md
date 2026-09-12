GitHub and manuscript workflow

The repository is initialized locally on `main`. No GitHub owner, remote URL, or authenticated push is configured in the starter. Use the GitHub connection when available, or the manual steps below. Do not place tokens in files, commit messages, or remote URLs.

**First push.**

1. Unzip the starter project if working on your laptop. The archive includes local Git history.
2. On GitHub, create an empty repository named `jrdb-patrol-alerts` under your chosen account. Private is the suggested starting visibility. Do not initialize another README, license, or ignore file; this project already contains a commit history. [GitHub repository creation guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
3. In the project directory, inspect the history and configure your own identity for future commits. Replace the example name/email with your actual chosen Git identity; GitHub offers a private noreply address in account email settings.

```bash
cd ~/jrdb-patrol-alerts
git log --oneline
git status
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED OR GITHUB NOREPLY EMAIL"
```

4. Replace `YOUR_USERNAME` below with the actual repository owner. Use your normal GitHub authentication setup. The following assumes no `origin` remote exists:

```bash
git remote add origin https://github.com/YOUR_USERNAME/jrdb-patrol-alerts.git
git push -u origin main
```

If a remote has already been configured, inspect it and use the correct existing remote rather than blindly adding or replacing it. Do not force-push unrelated histories. Account setup/authentication is separate from the repository files; no credentials are included in the starter.

**Every subsequent milestone.**

State the question or implementation change in an issue. Implement a bounded change, verify the specific behavior at risk, record the outcome, update the corresponding paper section, inspect the staged diff, commit, and push. Preserve failed or inconclusive experiments with accurate status.

Before an experiment, commit the exact code/configuration and ensure the working tree is clean. Use that commit as the run's input provenance. After the run, commit its small result artifacts and manuscript changes with the run ID. Keep raw media and large prediction caches excluded from Git.

```bash
git status --short
git diff
git add docs/experiment_log.md manifests/runs.csv paper/manuscript.md
git diff --cached --stat
git diff --cached
git commit -m "docs: record RUN_ID findings and update manuscript"
git push
```

This is an example for a documentation/results update. Add the specific implementation and configuration files relevant to a code change too. Replace `RUN_ID` with a real completed or failed run identifier. Do not claim a run was performed merely to fill the log.

For larger changes, a short-lived branch and pull request can keep `main` runnable. Small checked milestones can use direct commits while working alone. The aim is a recoverable research record, not maximum commit count.

**Writing alongside implementation.**

| Current work | Write now | Leave pending |
|---|---|---|
| Foundation | Motivation, task, questions, prior-work notes | Numerical abstract and claimed contributions |
| Geometry/data pilot | Dataset release, units, event definition, exclusions | Generalization claims |
| Baseline/method implementation | Exact algorithms and experimental design | Statements that a method is better |
| Frozen held-out runs | Tables, uncertainty, failures, effect interpretation | Any unperformed deployment claims |
| Final review | Evidence-based abstract, limitations, conclusions | Nothing reported as fact without evidence |

Do not add an automatic scheduled push task: pushes belong to the completed work in each session. Source code, manifests, manuscript, and small research records form the versioned project; dataset access remains through the official provider.
