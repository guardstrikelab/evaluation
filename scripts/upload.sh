#!/bin/bash

USAGE_STRING=$(cat <<- END
Usage: $0 [AWS_ACCESS_KEY_ID] [AWS_SECRET_ACCESS_KEY] [AWS_SESSION_TOKEN] [IMAGE_ID]
END
)

usage() { echo "$USAGE_STRING"; exit 1; }

if [ $# -ne 4 ]; then
  usage
fi

IMAGE_ID=$4

if [ -z "$IMAGE_ID" ]; then
  echo "( IMAGE_ID refers to REPOSITORY:TAG of an image. )"
  exit 1
fi

echo "Building docker"

if ! command -v curl &> /dev/null; then
  sudo apt-get update
  sudo apt-get install curl
fi

if command -v aws &> /dev/null; then
  echo "AWS CLI installed."; 
else 
  echo "Installing AWS CLI";
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip awscliv2.zip
  sudo ./aws/install
fi

export AWS_ACCESS_KEY_ID=$1
export AWS_SECRET_ACCESS_KEY=$2
export AWS_SESSION_TOKEN=$3

aws ecr get-login-password --region cn-northwest-1 | docker login --username AWS --password-stdin 508001631881.dkr.ecr.cn-northwest-1.amazonaws.com.cn

docker exec -it oasis-dora sh -c 'if [ -f /home/dora/workspace/simulate/team_code/dora-drives/graphs/oasis/output01.avi ]; then rm /home/dora/workspace/simulate/team_code/dora-drives/graphs/oasis/output01.avi; fi'

docker commit oasis-dora oasis-dora:tmp

docker run --gpus all --runtime=nvidia --net=host -itd --shm-size=2g --memory=5g --name dora-oasis-container oasis-dora:tmp /bin/bash

docker cp team_code dora-oasis-container:/home/dora/workspace/simulate

docker commit dora-oasis-container $IMAGE_ID

docker push $IMAGE_ID

docker rm -f dora-oasis-container

docker rmi oasis-dora:tmp