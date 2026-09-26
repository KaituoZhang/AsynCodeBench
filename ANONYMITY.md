# Double-Blind Review Artifact

This branch is the source for the anonymous review artifact. During review:

- use only the Anonymous GitHub URL published with the submission;
- do not link the maintainer repository, contributor pages, project website,
  personal package registries, or public development branches;
- identify human annotators only with stable labels such as `annotator_a`;
- use repository-relative paths or neutral examples such as
  `/path/to/AsynCodeBench`;
- treat public Commit0 and OpenHands namespaces as third-party dependencies,
  not as project authorship;
- reconstruct compiler images locally until a neutral public registry
  namespace is available.

Run the built-in audit before every update:

```bash
python scripts/check_anonymity.py
```

Maintainers should additionally create an untracked
`.anonymous-private-terms` file containing one name, username, email address,
institution, or other private literal per line. The audit reads that file but
never prints its contents. The file is excluded by `.gitignore`.

After updating the source repository, refresh the anonymous mirror, download
its ZIP in an incognito session, and run the same checks on the downloaded
artifact. Re-enable citations, contributor links, website links, and
first-party registry aliases only after the review period ends.
