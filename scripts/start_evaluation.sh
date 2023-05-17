#!/bin/bash

SCRIPT_ROOT=${SCRIPT_ROOT:-/path/to/script/root}
TEAM_CODE_ROOT=${TEAM_CODE_ROOT:-/path/to/team/code/root}
START_SCRIPT_URL=${START_SCRIPT_URL:-https://example.com/start_script.sh}

cd "${SCRIPT_ROOT}" || exit

if ! command -v aws &> /dev/null; then
  echo "Installing AWS CLI"
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip awscliv2.zip
  sudo ./aws/install
fi

export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
export AWS_DEFAULT_REGION=cn-northwest-1

echo "AWS CLI is installed"

sudo apt-get update

if ! command -v zip &> /dev/null; then
  echo "Installing zip"
  sudo apt-get install -y zip
fi

if ! command -v jq &> /dev/null; then
  echo "Installing jq"
  sudo apt-get install -y jq
fi

cd "${TEAM_CODE_ROOT}" || exit

rm -rf "${SCRIPT_ROOT}/scenarios" "${SCRIPT_ROOT}/destination" "${SCRIPT_ROOT}/criterias"

if ! command -v ossutil64 &> /dev/null; then
  echo "Downloading ossutil64"
  aws s3 cp s3://carsmos-ningxia/ossutil64 "${SCRIPT_ROOT}/ossutil64"
  chmod +x "${SCRIPT_ROOT}/ossutil64"
fi

"${SCRIPT_ROOT}/ossutil64" config -i xxx -k xxx -e oss-cn-beijing.aliyuncs.com

# Enable the monitoring script to monitor the memory and video memory of the machine
bash "${SCRIPT_ROOT}/monitor.sh" &

aws s3 cp "${START_SCRIPT_URL}" "${SCRIPT_ROOT}/run_evaluation.sh"

sudo chmod +x "${SCRIPT_ROOT}/run_evaluation.sh"

bash "${SCRIPT_ROOT}/run_evaluation.sh"
