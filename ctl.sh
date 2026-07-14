#!/bin/bash
# my-agent-app control script
# Usage: ./ctl.sh [start|stop|restart|status|logs]

cd "$(dirname "$0")"
PORT=8000
FRONTEND_PORT=5173
LOG_FILE="/tmp/chainlit.log"
FRONTEND_LOG="/tmp/vite.log"
NODE_BIN="$(pwd)/.node/bin"

case "$1" in
  start)
    # Start backend
    if lsof -ti:$PORT >/dev/null 2>&1; then
      echo "Backend already running on port $PORT"
    else
      source venv/bin/activate
      nohup chainlit run app.py --port $PORT > $LOG_FILE 2>&1 &
      sleep 3
      if lsof -ti:$PORT >/dev/null 2>&1; then
        echo "Backend started — http://localhost:$PORT"
      else
        echo "Backend failed — check $LOG_FILE"
      fi
    fi
    # Start frontend
    if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
      echo "Frontend already running on port $FRONTEND_PORT"
    else
      export PATH="$NODE_BIN:$PATH"
      cd frontend
      nohup npx vite --port $FRONTEND_PORT > $FRONTEND_LOG 2>&1 &
      cd ..
      sleep 2
      if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
        echo "Frontend started — http://localhost:$FRONTEND_PORT"
      else
        echo "Frontend failed — check $FRONTEND_LOG"
      fi
    fi
    ;;
  stop)
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ -z "$PID" ]; then
      echo "Backend not running"
    else
      kill -9 $PID 2>/dev/null
      echo "Backend stopped"
    fi
    FPID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null)
    if [ -n "$FPID" ]; then
      kill -9 $FPID 2>/dev/null
      echo "Frontend stopped"
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  status)
    PID=$(lsof -ti:$PORT 2>/dev/null)
    FPID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null)
    if [ -z "$PID" ]; then
      echo "Backend: not running"
    else
      echo "Backend: running (PID $PID) — http://localhost:$PORT"
    fi
    if [ -z "$FPID" ]; then
      echo "Frontend: not running"
    else
      echo "Frontend: running (PID $FPID) — http://localhost:$FRONTEND_PORT"
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
