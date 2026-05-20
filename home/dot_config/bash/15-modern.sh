# ~/.config/bash/15-modern.sh
# Modern CLI tools — every alias guarded with command -v so missing tools degrade gracefully.

# eza → drop-in replacement for ls. Override the baseline aliases when present.
if command -v eza >/dev/null 2>&1; then
    alias ls='eza --group-directories-first'
    alias ll='eza -lah --git --group-directories-first'
    alias la='eza -A --group-directories-first'
    alias lt='eza --tree --level=2 --group-directories-first'
    alias lg='eza -lah --git --group-directories-first'
fi

# bat → cat with syntax highlighting. Don't override `cat` (scripts).
if command -v batcat >/dev/null 2>&1; then
    alias bat='batcat'
fi

# fd → user-friendly find. Ubuntu installs it as fdfind.
if command -v fdfind >/dev/null 2>&1 && ! command -v fd >/dev/null 2>&1; then
    alias fd='fdfind'
fi

# ripgrep aliases.
if command -v rg >/dev/null 2>&1; then
    alias rgi='rg -i'
fi

# zoxide → smarter cd. `cd` rebound (absolute paths still work because zoxide falls through to builtin cd).
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash --cmd cd)"
    # `cdi` for interactive selection across all known dirs.
    alias cdi='cd -i'
fi

# delta is wired up via ~/.gitconfig (core.pager); no shell alias needed.

# ---- fzf-driven git helpers (loaded only when both fzf and git are present) ----
if command -v fzf >/dev/null 2>&1 && command -v git >/dev/null 2>&1; then

    # gco — fuzzy branch (local + remote) checkout.
    gco() {
        local branch
        branch=$(git branch --all --color=never --sort=-committerdate \
            | sed 's/^[* ] //' \
            | sed 's|remotes/origin/||' \
            | awk '!seen[$0]++' \
            | grep -v '^HEAD ->' \
            | fzf --height=40% --reverse --prompt='branch> ') || return
        git switch "$branch" 2>/dev/null || git switch -c "$branch" --track "origin/$branch"
    }

    # gcoh — fuzzy commit checkout (detached HEAD).
    gcoh() {
        local sha
        sha=$(git log --color=always --oneline --decorate -n 200 \
            | fzf --ansi --height=40% --reverse --prompt='commit> ' \
            | awk '{print $1}') || return
        [ -n "$sha" ] && git checkout "$sha"
    }

    # gshow — fuzzy commit show with delta.
    gshow() {
        local sha
        sha=$(git log --color=always --oneline --decorate -n 500 \
            | fzf --ansi --height=40% --reverse --prompt='show> ' \
            | awk '{print $1}') || return
        [ -n "$sha" ] && git show "$sha"
    }

    # gfiles — fuzzy-pick a changed file and open in $EDITOR.
    gfiles() {
        local file
        file=$(git status --porcelain | awk '{print $2}' \
            | fzf --height=40% --reverse --prompt='file> ') || return
        [ -n "$file" ] && ${EDITOR:-vi} "$file"
    }

    # gkill — fuzzy-pick local branches (multi-select) and delete.
    gkill() {
        local branches
        branches=$(git branch --color=never \
            | sed 's/^[* ] //' \
            | grep -v '^main$\|^master$' \
            | fzf --multi --height=40% --reverse --prompt='delete> ')
        [ -n "$branches" ] && echo "$branches" | xargs -r git branch -D
    }
fi
