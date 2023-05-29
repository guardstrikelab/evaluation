#!/bin/bash

sudo apt-get install bc

CARLA_IP=xxx
AWS_KEY_ID=xxx
AWS_SECRET_KEY=xxx
AUTHORIZATION=xxx

current_date=$(date +%Y%m%d)
target_date="20230730"
if [[ $current_date -lt $target_date ]]; then
    EXERCISE=true
else
    EXERCISE=false
fi

if [ "$EXERCISE" = true ]; then
    for((i=1;i<=10;i++));
    do
        aws s3 cp s3://carsmos-ningxia/`aws s3api list-objects-v2 --bucket carsmos-ningxia --prefix exercise | jq ".Contents[$i].Key" | sed 's/"//g' ` ${SCRIPT_ROOT}/scenarios/
    done
else
    for((i=1;i<=10;i++));
    do
        aws s3 cp s3://carsmos-ningxia/`aws s3api list-objects-v2 --bucket carsmos-ningxia --prefix scenarios | jq ".Contents[$i].Key" | sed 's/"//g' ` ${SCRIPT_ROOT}/scenarios/
    done
fi

SCENARIO_COUNT=$(ls -l "${SCRIPT_ROOT}"/scenarios | wc -l)

for((j=1;j<=38;j++));
do
    aws s3 cp s3://carsmos-ningxia/$(aws s3api list-objects-v2 --bucket carsmos-ningxia --prefix destination | jq ".Contents[$j].Key" | sed 's/"//g' ) ${SCRIPT_ROOT}/destination/
    aws s3 cp s3://carsmos-ningxia/$(aws s3api list-objects-v2 --bucket carsmos-ningxia --prefix criteria | jq ".Contents[$j].Key" | sed 's/"//g' ) ${SCRIPT_ROOT}/criterias/
done

source ~/.bashrc
RESULT_DIR='/home/dora/workspace/simulate/result'

if [ -d $RESULT_DIR ]; then
  rm -rf $RESULT_DIR/*
fi



source /home/dora/.bashrc
if [ -f /home/dora/workspace/simulate/xosc/env.sh ]; then
    source /home/dora/workspace/simulate/xosc/env.sh
elif [ -f /home/dora/workspace/simulate/xosc/env ]; then
    # 读取env文件
    env_file="/home/dora/workspace/simulate/xosc/env"
    env_lines=($(cat $env_file))

    # 分别设置环境变量
    export SIMULATE="${env_lines[0]}"
    export YAML="${env_lines[1]}"
    export TEAM_AGENT="${env_lines[2]}"
    export TEAM_AGENT_CONF="${env_lines[3]}"
else 
    export SIMULATE="/home/dora/workspace/simulate/simulate.py"
    export YAML="/home/dora/workspace/simulate/team_code/dora-drives/graphs/oasis/oasis_agent.yaml"
    export TEAM_AGENT="/home/dora/workspace/simulate/team_code/dora-drives/carla/oasis_agent.py"
    export TEAM_AGENT_CONF="human_agent_config.txt"
fi

if [ -z "$YAML" ] || [ -z "$TEAM_AGENT" ]; then
    export SIMULATE="/home/dora/workspace/simulate/simulate.py"
    export YAML="/home/dora/workspace/simulate/team_code/dora-drives/graphs/oasis/oasis_agent.yaml"
    export TEAM_AGENT="/home/dora/workspace/simulate/team_code/dora-drives/carla/oasis_agent.py"
    export TEAM_AGENT_CONF="human_agent_config.txt"
fi

export TEAM_YAML=$YAML
export TEAM_AGENT_CONFIG=$TEAM_AGENT_CONF

echo "SIMULATE=$SIMULATE"
echo "YAML=$YAML"
echo "TEAM_AGENT=$TEAM_AGENT"
echo "TEAM_AGENT_CONF=$TEAM_AGENT_CONF"

export SIMULATE="/home/dora/workspace/simulate/simulate.py"
export enWvBzYQms=$CARLA_IP
export DISPLAY=""
if [ -z "$TEAM_AGENT_CONF" ]; then
    export TEAM_AGENT_CONF="1" 
fi
if [ -d /home/dora/workspace/simulate/team_code/dora-drives/result_csv ];then
    sudo chmod -R 777 /home/dora/workspace/simulate/team_code/dora-drives/result_csv
fi

FINISHED=0 # 表示完成了多少个场景

# Run for $REPEAT_TIME times
for((REPEAT=1;REPEAT<=${REPEAT_TIME};REPEAT++));
do
    for scenario in `ls ${SCRIPT_ROOT}/scenarios`
    do
        echo "============== Now simulating $scenario with Dora, time: $REPEAT=============="
        export XOSC=${SCRIPT_ROOT}/scenarios/$scenario

        # export CRITERIA=${SCRIPT_ROOT}/criterias/train_criterion.json
        export CRITERIA=${SCRIPT_ROOT}/criterias/${scenario%.*}.json

        export DESTINATION=`cat ${SCRIPT_ROOT}/destination/destination_${scenario%.*}`
        export DISTINATION=`cat ${SCRIPT_ROOT}/destination/destination_${scenario%.*}`
        echo "scenario: $XOSC"
        echo "criteria: $CRITERIA"
        echo "destination: $DESTINATION"
        if [ -f "${TEAM_CODE_ROOT}/dora-drives/graphs/oasis/output.avi" ]; then
            rm ${TEAM_CODE_ROOT}/dora-drives/graphs/oasis/output.avi
        fi
        if [ -f "${TEAM_CODE_ROOT}/dora-drives/graphs/oasis/output01.avi" ]; then
            rm ${TEAM_CODE_ROOT}/dora-drives/graphs/oasis/output01.avi
        fi

        echo "executing: bash /home/dora/workspace/simulate/team_code/dora-drives/cloud_dora_run.sh"
        # bash /home/dora/workspace/simulate/team_code/dora-drives/cloud_dora_run.sh
        dora up
        dora start $YAML --attach

        if [ ! -d $RESULT_DIR ] || [ `ls -a $RESULT_DIR | wc -l` -eq 0 ]; then
            echo "================= No result file, simulation failed ================="
            exit 1
        fi

        echo "============== Uploading ${scenario%.*}_output_data.csv =============="
        bash ${SCRIPT_ROOT}/s3upload.sh AWS_KEY_ID AWS_SECRET_KEY carsmos-ningxia@cn-northwest-1 ${TEAM_CODE_ROOT}/dora-drives/result_csv/_output_data.csv results/${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}/repeat-$REPEAT/${scenario%.*}_output_data.csv

        # # 实时上传进度
        tem_progress=$(echo "scale=4; $FINISHED/($REPEAT_TIME*$SCENARIO_COUNT)*100" | bc)
        progress=$(printf "%.2f" $tem_progress)

        # #使用curl命令发送POST请求
        if [[ ${ECR_REPOSITORY_NAME} == *staging* ]]; then
            imageId=$(echo $ECR_REPOSITORY_NAME:$ECR_IMAGE_TAG | sed 's/^\(.\{7\}\)./\1\//' | sed 's/^\(.\{16\}\)./\1\//')
            curl -k -X POST -H 'Content-Type:application/json' -H "Authorization:'Basic ${AUTHORIZATION}'" -d '{"imageId":"'"$imageId"'", "progress":'$progress'}' https://staging.carsmos.cn/api/submit
        else
            imageId=$(echo $ECR_REPOSITORY_NAME:$ECR_IMAGE_TAG | sed 's/^\(.\{8\}\)./\1\//')
            curl -k -X POST -H 'Content-Type:application/json' -H "Authorization:'Basic ${AUTHORIZATION}'" -d '{"imageId":"'"$imageId"'", "progress":'$progress'}' https://race.carsmos.cn/api/submit
        fi

        # 上传回放
        if [ -d /home/dora/workspace/simulate/viz_data ]; then
            cd /home/dora/workspace/simulate
            cp -r viz_data ${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}-${scenario%.*}-$REPEAT
            ${SCRIPT_ROOT}/ossutil64 cp -r ${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}-${scenario%.*}-$REPEAT oss://sdg-bags/oasisbags/${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}-${scenario%.*}-$REPEAT
            cd ${TEAM_CODE_ROOT}
        fi

        ((FINISHED++))

        dora destroy
    done

    echo "============== $REPEAT th simulation finished. =============="

    for FILE in `ls $RESULT_DIR`
    do
        if echo $FILE | grep -q -E '\.json$'
        then
        echo "============== Uploading $FILE =============="
        bash ${SCRIPT_ROOT}/s3upload.sh AWS_KEY_ID AWS_SECRET_KEY carsmos-ningxia@cn-northwest-1 $RESULT_DIR/$FILE results/${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}/repeat-$REPEAT/$FILE
        fi
    done

    sudo rm -rf $RESULT_DIR

    docker restart carla
done

echo "================= Simulation Finished ================="

# Upload the user's algorithm code (Team code folder)
cd ${TEAM_CODE_ROOT}
zip -rq ${SCRIPT_ROOT}/team_code.zip .
bash ${SCRIPT_ROOT}/s3upload.sh AWS_KEY_ID AWS_SECRET_KEY carsmos-ningxia@cn-northwest-1 ${SCRIPT_ROOT}/team_code.zip results/${ECR_REPOSITORY_NAME}-${ECR_IMAGE_TAG}/team_code.zip
