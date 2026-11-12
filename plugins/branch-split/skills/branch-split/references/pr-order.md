# PR order: reply format and rules

Use this after `split.py pushed <spec>` passes. Keep the reply short. Use one table per repo, then the rules once.

## Per repo

```markdown
**<APP>: cut from `<base>`, PR into `<pr_target>`**
| PR | Branch | PR base |
|---|---|---|
| 1 | `Chore/<APP>/Repo-Clean-Up` | <pr_target> |
| 6 | `BugFix/<APP>/INC0112029-App-Crash` | <pr_target> |
| 7 | `BugFix/<APP>/INC0113265-General-Contact` | #6, then <pr_target> |
```

`split.py pushed` prints this table, with the merge-order bullets, for you to paste.

## Rules

- **Order:**
  - PRs based on the target branch are independent and can merge in any order.
  - A stacked PR ("#n, then target") waits for its parent PR to merge.
  - After the parent merges, retarget the stacked PR to the target. If the parent's branch is deleted on merge, GitHub retargets it automatically.
- **Opening a stacked PR:** its base is the parent branch, so the diff shows only its own change.
- **Merge method:** use "Create a merge commit" for a parent that has stacked children, and for the children themselves. A squash makes the child show the parent's changes again, and the child then needs a rebase.
- **Integration branch:** when the target is not the default branch (for example `Enhance/FrameworkUpgrade`), open one PR from it into `develop` only after every ticket PR is merged and tested.
- **Branches already merged before:** an old merged branch with the same name needs a new PR. Don't reopen the old one.
- **After merge:**
  - drop the backup stash: `git stash list | grep split-backup`, then `git stash drop stash@{N}`;
  - delete the output folder.
- **Backend dependencies:** list any API, label or config change the branches rely on, so it ships before or with the app release.
