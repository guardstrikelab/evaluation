import json
import time

import boto3 as boto3
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
    jobQueue = event['detail']['jobQueue']
    status = event['detail']['status']
    image = event['detail']['container']['image']
    image_id = str(image[image.index('/') + 1:])
    if image_id.startswith("staging"): return
    image_repository = image_id[:image_id.index(':')]
    image_tag = image_id[image_id.index(':') + 1:]

    if jobQueue == "xxx":
        if status == 'RUNNABLE':
            params = {
                "imageId": image_id,
                "status": "INIT"
            }
            http.request('POST', api, headers=headers, body=json.dumps(params))
            print("RUNNABLE")
        elif status == 'STARTING':
            params = {
                "imageId": image_id,
                "status": "PULLING"
            }
            http.request('POST', api, headers=headers, body=json.dumps(params))
            print("STARTING")
        elif status == 'RUNNING':
            params = {
                "imageId": image_id,
                "status": "RUNNING"
            }
            http.request('POST', api, headers=headers, body=json.dumps(params))
            print("RUNNING")
        elif status == 'SUCCEEDED':
            params = {
                "imageId": image_id,
                "status": "SUCCEEDED",
                "scenario_results": []
            }
            http.request('POST', api, headers=headers, body=json.dumps(params))
            total_sim_time = 0  # 所有场景的仿真时长之和（秒）
            total_mileage = 0  # 所有场景的里程之和（米）
            score_sum = 0  # 所有场景得分之和
            success = 0  # 成功的场景数量
            fail = 0  # 失败的场景数量
            s3 = boto3.client('s3')

            # 从s3获取所有的场景结果文件
            list_response = s3.list_objects_v2(
                Bucket='carsmos-ningxia',
                Prefix='results/{}-{}'.format(image_repository.replace("/", "-"), image_tag),
            )
            scenario_count = 0

            # 遍历每个结果文件，综合到一个dist对象中：scenario_result
            for content in list_response['Contents']:
                scenario_result = {}
                file_name = str(content['Key'])
                if 'viz_data' in file_name or not file_name.endswith(".json"): continue
                repeat = int(file_name[file_name.index("repeat-") + 7: file_name.index("repeat-") + 8])
                scenario_count += 1
                bucket = 'carsmos-ningxia'
                response = s3.get_object(
                    Bucket=bucket,
                    Key=file_name
                )
                body = response['Body']
                result = json.loads(body.read())
                print({'simulation_result': result})

                # 开始解析单个场景的result.json
                summary = result['summary']
                scenario_name = result['scenario']
                criteria = result['criteria']

                scenario_sim_time = round(summary['game_time_duration'])
                total_sim_time += scenario_sim_time
                scenario_score = summary['score']
                score_sum += scenario_score
                if summary['success']:
                    success += 1
                else:
                    fail += 1

                # 解析scenario_result的参数
                scenario_mileage = 0
                time_cost_score = 100
                run_red_light_score = 100
                on_road_score = 100
                onto_solid_line_score = 100
                collision_score = 100
                velocity_score = 100
                acceleration_longitudinal_score = 100
                acceleration_lateral_score = 100  # 横向加速度
                jerk_longitudinal_score = 100  # 纵向加速度变化率
                jerk_lateral_score = 100
                reach_destination_score = 100
                ego_events = []
                for criterion in criteria:
                    criterion_name = criterion['name']
                    if criterion_name == 'DrivenDistanceTest':
                        scenario_mileage = criterion['actual_value']
                        total_mileage += scenario_mileage
                    elif criterion_name == 'RunRedLightTest':
                        run_red_light_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "闯红灯",
                                    "event_desc": "主车在（x: {}, y: {}, z: {}）处闯红灯，红灯id是{}"
                                        .format(event['location']['x'], event['location']['y'], event['location']['z'],
                                                event['object_id']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'OnRoadTest':
                        on_road_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "驶出行车道",
                                    "event_desc": "主车在（x: {}, y: {}, z: {}）处驶出行车道"
                                        .format(event['location']['x'], event['location']['y'], event['location']['z']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'OntoSolidLineTest':
                        onto_solid_line_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "压实线",
                                    "event_desc": "主车在（x: {}, y: {}, z: {}）处越过实线"
                                        .format(event['location']['x'], event['location']['y'], event['location']['z']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'CollisionTest':
                        collision_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                if event['object_name']:
                                    ego_event = {
                                        "event_name": "碰撞",
                                        "event_desc": "主车在（x: {}, y: {}, z: {}）处与id为{}，类型为{}，名称为{}的对象发生碰撞"
                                            .format(event['location']['x'], event['location']['y'],
                                                    event['location']['z'],
                                                    event['object_id'], event['object_type'], event['object_name']),
                                        "event_time": format_event_time(event)
                                    }
                                else:
                                    ego_event = {
                                        "event_name": "碰撞",
                                        "event_desc": "主车在（x: {}, y: {}, z: {}）处与id为{}，类型为{}的对象发生碰撞"
                                            .format(event['location']['x'], event['location']['y'],
                                                    event['location']['z'],
                                                    event['object_id'], event['object_type']),
                                        "event_time": format_event_time(event)
                                    }
                                ego_events.append(ego_event)
                    elif criterion_name == 'MaxVelocityTest':
                        # MaxVelocityTest和MinVelocityTest的得分会保持一致
                        velocity_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "超过速度上限",
                                    "event_desc": "主车超过了速度上限，主车速度：{} km/h，速度上限：{} km/h"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'MinVelocityTest':
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "低于速度下限",
                                    "event_desc": "主车速度低于下限，主车速度：{} km/h，速度下限：{} km/h"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'AccelerationLongitudinalTest':
                        acceleration_longitudinal_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "超过纵向加速度上限",
                                    "event_desc": "主车以 {} m/s^2 超过了纵向加速度上限 {} m/s^2"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'AccelerationLateralTest':
                        acceleration_lateral_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "超过横向加速度上限",
                                    "event_desc": "主车以 {} m/s^2 超过了横向加速度上限 {} m/s^2"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'JerkLongitudinalTest':
                        jerk_longitudinal_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "超过纵向加速度变化率上限",
                                    "event_desc": "主车以 {} m/s^3 超过了纵向加速度变化率上限 {} m/s^2"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'JerkLateralTest':
                        jerk_lateral_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "超过横向加速度变化率上限",
                                    "event_desc": "主车以 {} m/s^3 超过了横向加速度变化率上限 {} m/s^3"
                                        .format(event['event_value'], criterion['expected_value_success']),
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == 'ReachDestinationTest':
                        reach_destination_score = criterion['score']
                        if len(criterion['ego_event_list']) > 0:
                            for event in criterion['ego_event_list']:
                                ego_event = {
                                    "event_name": "到达终点",
                                    "event_desc": "主车到达终点",
                                    "event_time": format_event_time(event)
                                }
                                ego_events.append(ego_event)
                    elif criterion_name == "TimeoutTest":
                        time_cost_score = criterion['score']

                scenario_result.update({
                    "scenario_name": scenario_name + ": repeat-{}".format(repeat),
                    # "index": repeat,
                    "sim_time": scenario_sim_time,
                    "mileage": scenario_mileage,
                    "success": summary['success'],
                    "scenario_score": scenario_score,
                    "time_cost_score": time_cost_score,
                    "run_red_light_score": run_red_light_score,
                    "on_road_score": on_road_score,
                    "onto_solid_line_score": onto_solid_line_score,
                    "collision_score": collision_score,
                    "velocity_score": velocity_score,
                    "acceleration_longitudinal_score": acceleration_longitudinal_score,
                    "acceleration_lateral_score": acceleration_lateral_score,
                    "jerk_longitudinal_score": jerk_longitudinal_score,
                    "jerk_lateral_score": jerk_lateral_score,
                    "reach_destination_score": reach_destination_score,
                    "ego_events": ego_events
                })

                params['scenario_results'].append(scenario_result)
                params['total_sim_time'] = int(total_sim_time)
                params['total_mileage'] = total_mileage
                params['score'] = round(score_sum / scenario_count, 2)
                params['approved'] = True
                params['success'] = success
                params['fail'] = fail

            ra = http.request('POST', api, headers=headers, body=json.dumps(params))
            print({
                'status': ra.status,
                'params': params,
                'response': ra.data
            })

        elif status == 'FAILED':
            params = {
                "imageId": image_id,
                "status": "FAILED"
            }
            http.request('POST', api, headers=headers, body=json.dumps(params))
            print("FAILED")

    print(event)
    return event


def format_event_time(event):
    return "{}.{}".format(
        time.strftime("%M:%S", time.gmtime(event['game_time'])),
        str(event['game_time'] % 1)[2:4])


def updateProgress(image_id):
    image_repository = image_id[:image_id.index(':')]
    image_tag = image_id[image_id.index(':') + 1:]
    s3 = boto3.client('s3')

    # 从s3获取所有的场景结果文件
    object_response = s3.get_object(
        Bucket='carsmos-ningxia',
        Key='results/{}-{}/FINISHED'.format(image_repository.replace("/", "-"), image_tag),
    )
    body = object_response['Body']
    result = int(body.read())
    total = 10
    progress = round(result / total * 100, 2)
    params = {
        "imageId": image_id,
        "progress": progress
    }
    http.request('POST', api, headers=headers, body=json.dumps(params))
