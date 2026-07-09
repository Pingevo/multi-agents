#!/bin/bash
# my-agent-app control script
# Usage: ./ctl.sh [start|stop|restart|status|logs]

cd "$(dirname "$0")"
PORT=8000
LOG_FILE="/tmp/chainlit.log"

case "$1" in
  start)
    if lsof -ti:$PORT >/dev/null 2>&1; then
      echo "Already running on port $PORT"
      exit 0
    fi
    source venv/bin/activate
    nohup chainlit run app.py --port $PORT > $LOG_FILE 2>&1 &
    sleep 3
    if lsof -ti:$PORT >/dev/null 2>&1; then
      echo "Started — http://localhost:$PORT"
    else
      echo "Failed to start — check $LOG_FILE"
    fi
    ;;
  stop)
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ -z "$PID" ]; then
      echo "Not running"
    else
      kill -9 $PID 2>/dev/null
      echo "Stopped"
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  status)
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ -z "$PID" ]; then
      echo "Not running"
    else
      echo "Running (PID $PID) — http://localhost:$PORT"
    fi
    ;;
  logs)
    tail -f $LOG_FILE
    ;;
  *)
    echo "Usage: ./ctl.sh [start|stop|restart|status|logs]"
    exit 1
    ;;
esac
