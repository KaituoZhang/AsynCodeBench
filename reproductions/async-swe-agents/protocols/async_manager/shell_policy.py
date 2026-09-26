# ruff: noqa: E501
"""Pinned shell parser vendored for Async-Manager; no cross-checkout imports.

Source: released CAID read-only parser, copied without changing its policy.
"""

_READ_ONLY_MANAGER_GUARD_PROGRAM = r"""
import json
import re
import shlex
import sys


POLICY_VERSION = "caid-manager-read-only-v2"


def deny(reason):
    print(json.dumps({
        "decision": "deny",
        "reason": "AsynCodeBench read-only manager policy (" + POLICY_VERSION + "): " + reason,
    }))
    raise SystemExit(0)


def allow():
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)


try:
    event = json.load(sys.stdin)
except Exception as error:
    deny("could not parse the tool request: " + str(error))

if str(event.get("tool_name") or "") != "terminal":
    allow()

tool_input = event.get("tool_input") or {}
command = tool_input.get("command")
if not isinstance(command, str) or not command.strip():
    deny("terminal requests must contain one explicit command string")

# Multiline shell programs, command substitution, background jobs, and output
# redirection make reliable static authorization impossible.  A read-only
# manager does not need them: issue one inspection pipeline per tool call.
if "\n" in command or "\r" in command:
    deny("multiline shell programs and heredocs are disabled; use one read-only command per call")
if "$(" in command or "`" in command:
    deny("shell command substitution is disabled in the manager workspace")

try:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
except ValueError as error:
    deny("could not safely parse terminal command: " + str(error))

if not tokens:
    deny("empty terminal command")

for token in tokens:
    # shlex keeps fd-prefixed redirects such as 2>/tmp/log in one token.
    if token in {">", ">>", ">|", "<>", "<<", "<<<", "&>", "&>>"}:
        deny("shell redirection and heredocs are disabled")
    if re.match(r"^(?:\d+)?(?:>|>>|>\||<>|>&|&>|&>>)", token):
        deny("output redirection is disabled")
    if token in {"&", "(", ")", "{", "}"}:
        deny("background jobs and compound shell programs are disabled")

separators = {"&&", "||", ";", "|"}
segments = []
current = []
for token in tokens:
    if token in separators:
        if not current:
            deny("empty shell pipeline segment")
        segments.append(current)
        current = []
    else:
        current.append(token)
if not current:
    deny("empty shell pipeline segment")
segments.append(current)

allowed_commands = {
    ":", "[", "basename", "cat", "cd", "cmp", "cut", "date", "df", "diff",
    "dirname", "du", "echo", "false", "file", "find", "git", "grep",
    "head", "id", "jq", "ls", "printf", "pwd", "py.test", "pytest", "readlink",
    "realpath", "rg", "sed", "sort", "stat", "tail", "test", "tr",
    "tree", "true", "uname", "wc", "whereis", "which",
}
allowed_git_subcommands = {
    "blame", "cat-file", "check-attr", "check-ignore", "describe", "diff",
    "diff-files", "diff-index", "diff-tree", "for-each-ref", "grep", "help",
    "log", "ls-files", "merge-base", "name-rev", "rev-parse", "shortlog",
    "show", "show-ref", "status", "version",
}


def first_command_index(segment):
    index = 0
    while index < len(segment) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", segment[index]):
        index += 1
    return index


def git_subcommand(segment, index):
    index += 1
    while index < len(segment):
        token = segment[index]
        if token in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
            index += 2
            continue
        if token.startswith(("--git-dir=", "--work-tree=", "--namespace=")):
            index += 1
            continue
        if token in {"--no-pager", "--paginate", "--literal-pathspecs", "--no-optional-locks"}:
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token.lower()
    return None


for segment in segments:
    index = first_command_index(segment)
    if index >= len(segment):
        deny("environment assignments without an inspection command are disabled")
    executable = segment[index].rsplit("/", 1)[-1].lower()

    if executable in {"python", "python3"}:
        args = segment[index + 1:]
        if len(args) < 2 or args[0] != "-m" or args[1] not in {"pytest", "unittest"}:
            deny("Python is limited to `python -m pytest` or `python -m unittest`")
    elif executable not in allowed_commands:
        deny("command `" + executable + "` is not in the read-only inspection allowlist")

    args = segment[index + 1:]
    if executable == "git":
        if "-c" in args:
            deny("per-command Git configuration is disabled")
        subcommand = git_subcommand(segment, index)
        if subcommand not in allowed_git_subcommands:
            deny("Git subcommand `" + str(subcommand) + "` can change repository state")
        if any(
            arg in {"--ext-diff", "--output", "--textconv"}
            or arg.startswith("--output=")
            for arg in args
        ):
            deny("Git external commands and output files are disabled")
    elif executable == "find":
        if any(arg in {
            "-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprintf",
            "-fprint", "-fprint0", "-fls",
        }
               for arg in args):
            deny("mutating or file-output `find` actions are disabled")
    elif executable == "sed":
        if any(
            arg == "--in-place"
            or arg.startswith("--in-place=")
            or (re.match(r"^-[^-]+$", arg) and "i" in arg[1:])
            for arg in args
        ):
            deny("in-place sed editing is disabled")
    elif executable == "sort":
        if any(arg in {"-o", "--output"} or arg.startswith("--output=") for arg in args):
            deny("sort output files are disabled")
    elif executable == "diff":
        if any(arg == "--output" or arg.startswith("--output=") for arg in args):
            deny("diff output files are disabled")
    elif executable == "tree":
        if "-o" in args or any(arg.startswith("--output=") for arg in args):
            deny("tree output files are disabled")
    elif executable in {"pytest", "py.test", "python", "python3"}:
        forbidden_outputs = (
            "--basetemp", "--junitxml", "--html", "--json-report-file",
            "--cov-report", "--result-log",
        )
        if any(any(arg == option or arg.startswith(option + "=") for option in forbidden_outputs)
               for arg in args):
            deny("test-runner output paths are disabled in the manager workspace")

allow()
"""
