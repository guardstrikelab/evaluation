import json
import time

import boto3
import urllib3

urllib3.disable_warnings()
headers = {
    'Authorization': 'xxx',
    'Content-Type': 'application/json',
    'Accept-Charset': 'utf-8'
}
http = urllib3.PoolManager(
    cert_reqs="CERT_NONE"
)
api = 'https://race.carsmos.cn/api/submit'


def lambda_handler(event, context):
    image_url = "{}.dkr.ecr.{}.amazonaws.com.cn/{}:{}".format(event['account'], event['region'],
                                                              event['detail']['repository-name'],
                                                              event['detail']['image-tag'])
    if 'staging' in image_url: return

    params = {
        "imageId": f"{event['detail']['repository-name']}:{event['detail']['image-tag']}",
        "status": "PENDING"
    }

    # If imageId is not specified by the registration system, return
    response = http.request('POST', api, headers=headers, body=json.dumps(params))
    if len(response.data) != 0:
        rjson = json.loads(response.data)
        print(f"signup server response: {rjson}")
        if 'message' in rjson and rjson['message'] == 'No Submission found':
            print(
                f"Wrong imageId {event['detail']['repository-name']}:{event['detail']['image-tag']} submitted by user.")
            return

    batch = boto3.client('batch')

    timestamp = str(int(time.time()))
    register_job_response = batch.register_job_definition(
        jobDefinitionName='carsmos-job-defination-development-{}-{}'.format(event['detail']['repository-name'],
                                                                            event['detail']['image-tag']).replace("/",
                                                                                                                  "-"),
        type='container',
        containerProperties={
            'image': image_url,
            'command': [
                'bash',
                '/carsmos/{}/script/start_evaluation_old.sh'.format(timestamp)
            ],
            'executionRoleArn': 'xxx',
            'environment': [
                {
                    'name': 'ECR_REPOSITORY_NAME',
                    'value': event['detail']['repository-name'].replace("/", "-")
                },
                {
                    'name': 'ECR_IMAGE_TAG',
                    'value': event['detail']['image-tag']
                },
                {
                    'name': 'CARLA_ROOT',
                    'value': '/carsmos/{}/carla'.format(timestamp)
                },
                {
                    'name': 'SCRIPT_ROOT',
                    'value': '/carsmos/{}/script'.format(timestamp)
                },
                {
                    'name': 'REPEAT_TIME',
                    'value': '1'
                },
                {
                    'name': 'TEAM_CODE_ROOT',
                    'value': '/home/dora/workspace/simulate/team_code'
                },
                {
                    'name': 'START_SCRIPT_URL',
                    'value': 's3://carsmos-ningxia/run_evaluation.sh'
                }
            ],
            'mountPoints': [
                {
                    'containerPath': '/carsmos/{}/carla'.format(timestamp),  # 为了避免用户覆盖用户自己创建的文件夹
                    'readOnly': True,
                    'sourceVolume': 'carla'
                },
                {
                    'containerPath': '/carsmos/{}/script'.format(timestamp),
                    'readOnly': False,
                    'sourceVolume': 'script'
                }
            ],
            'volumes': [
                {
                    'name': 'carla',
                    'host': {
                        'sourcePath': '/opt/CARLA'
                    }
                },
                {
                    'name': 'script',
                    'host': {
                        'sourcePath': '/opt/script'
                    }
                }
            ],
            'resourceRequirements': [
                {
                    'value': '12',
                    'type': 'VCPU'
                },
                {
                    'value': '30720',
                    'type': 'MEMORY'
                },
                {
                    'value': '1',
                    'type': 'GPU'
                }
            ],
            'privileged': True,
            'logConfiguration': {
                'logDriver': 'awslogs'
            },
            'linuxParameters': {
                'sharedMemorySize': 4096
            }
        }
    )

    print(register_job_response)

    response = batch.submit_job(
        jobName='carsmos-job-production-{}-{}'.format(event['detail']['repository-name'],
                                                      event['detail']['image-tag']).replace(
            "/", "-"),
        jobQueue='carsmos-production',
        jobDefinition=register_job_response['jobDefinitionArn'],
        timeout={
            'attemptDurationSeconds': 7200
        }
        # retryStrategy={
        #     'attempts': 3,
        #     'evaluateOnExit': [
        #         {
        #             'action': 'retry',
        #             'onExitCode': "1"
        #         }
        #     ]
        # }
    )
    print(response)
    return event, register_job_response, response
