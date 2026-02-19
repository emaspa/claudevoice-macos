# Claude Code Voice Notifications

This project provides voice notifications for Claude Code sessions. You can speak aloud to the user during important moments using the `--say` flag.

## How to speak

```bash
python3 "/Users/emanuele/claudvoice_macos/notify.py" --say "your message here"
```

Run this via Bash with `async: true` so it doesn't block your work.

## When to speak

Use voice notifications for actions the user would want to hear about while away from the screen:

- Pushing code to a remote repository
- Creating or merging a pull request
- Starting a deployment or long-running build
- Destructive operations (deleting branches, dropping data)
- Completing a multi-step task that took significant time
- Encountering a blocking error that needs user attention

## How to phrase messages

- Keep it to one short sentence, conversational tone
- Say what's meaningful — the action and its outcome
- Never read aloud file paths, commit hashes, URLs, or technical identifiers
- Match the personality in `personality.md` if one is active (currently Jarvis)

Good: "Pushed the feature branch to remote."
Good: "Pull request created for the authentication update."
Good: "Tests are failing — looks like a missing dependency."

Bad: "Pushed to origin/feature-auth at abc123."
Bad: "Created PR #47 at https://github.com/..."
Bad: "Error in /Users/emanuele/project/src/auth.py line 42."

## Don't over-notify

The voice is a brief status update, not a play-by-play. Only speak when the user gains something from hearing it. Reading a file, running a search, or making a small edit — those don't need narration.
