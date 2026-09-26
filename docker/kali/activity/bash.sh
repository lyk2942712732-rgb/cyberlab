# Sourced by /etc/bash.bashrc for interactive Bash sessions.
case $- in *i*) ;; *) return ;; esac
# Record each submitted command, including repeated and leading-space commands.
# PS0 executes once after Bash has read a complete command and before execution.
HISTCONTROL=
HISTIGNORE=
set -o history
shopt -s cmdhist lithist
__cyberlab_submit() {
    local command HISTTIMEFORMAT=''
    command=$(builtin history 1)
    # fc -1 deliberately skips the current command; history 1 includes it in PS0.
    if [[ $command =~ ^[[:space:]]*[0-9]+[[:space:]][[:space:]](.*)$ ]]; then
        command=${BASH_REMATCH[1]}
    else
        printf '%s\n' 'CyberLab 操作记录未保存：无法读取提交命令' >&2
        return 1
    fi
    printf '%s' "$command" | /usr/bin/python3 /usr/local/lib/cyberlab-activity/emit.py shell "$$"
}
PS0='$(__cyberlab_submit)'
/usr/bin/python3 /usr/local/lib/cyberlab-activity/emit.py shell-ready 2>/dev/null || true
