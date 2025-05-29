# my_worker.py
import os
import oss2
import time
import runpod
import urllib
import requests
import traceback
from backend.main import SubtitleRemover

ALIYUN_ACCESS_KEY_ID = os.environ.get('ALIYUN_ACCESS_KEY_ID')
ALIYUN_ACCESS_KEY_SECRET = os.environ.get('ALIYUN_ACCESS_KEY_SECRET')
ALIYUN_ENDPOINT = os.environ.get('ALIYUN_ENDPOINT')
ALIYUN_BUCKET_NAME = os.environ.get('ALIYUN_BUCKET_NAME')

auth = oss2.Auth(ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, ALIYUN_ENDPOINT, ALIYUN_BUCKET_NAME)


def down_file(url, save_folder, filename=None, chunk_size=1024*4):
    """
    下载文件(流式)
    """
    # 提取文件名
    if filename == None:
        filename = urllib.parse.unquote(
            urllib.parse.urlparse(url).path.split("/")[-1])

    # 创建保存文件夹
    if not os.path.exists(save_folder):
        os.makedirs(save_folder, exist_ok=True)

    # 下载文件
    save_filepath = os.path.join(save_folder, filename)
    with requests.get(url, stream=True) as req:
        raw_file_size = int(req.headers['Content-Length'])

        with open(save_filepath, 'wb') as f:
            for chunk in req.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    file_len = os.path.getsize(save_filepath)
    if file_len != raw_file_size:
        raise requests.exceptions.ConnectionError('下载文件连接中断，文件不完整')
    return save_filepath


def upload_to_aliyun(local_file_path, oss_file_path):
    """
    上传文件到阿里云OSS
    :param local_file_path: 本地文件路径
    :param job_id: job的ID，用于生成OSS目标文件路径
    :return: 上传成功返回文件的完整OSS路径，失败返回None
    """
    try:
        # 获取文件后缀
        # 生成OSS目标文件路径
        start_time = time.time()  # 记录开始时间
        # 上传文件
        result = bucket.put_object_from_file(oss_file_path, local_file_path)
        end_time = time.time()  # 记录结束时间
        elapsed_time = end_time - start_time  # 计算耗时
        if result.status == 200:
            print(f"成功上传到阿里云，耗时{elapsed_time}")
            # 返回https的完整OSS路径
            return f"https://{ALIYUN_BUCKET_NAME}.{ALIYUN_ENDPOINT}/{oss_file_path}"
        else:
            return None
    except Exception as e:
        print(f"上传文件到阿里云OSS失败: {e}")
        raise Exception(f"上传文件到阿里云OSS失败: {e}")


def is_even(job):
    result = {
        "status": 0,
        "output_video_url": None,
        "message": None
    }
    try:
        job = job.get("input", {})
        video_url = job["video_url"]
        video_path = down_file(video_url, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'))
        ymin = job.get('ymin', None)
        ymax = job.get('ymax', None)
        xmin = job.get('xmin', None)
        xmax = job.get('xmax', None)
        sub_area = None
        if all(v is not None for v in [ymin, ymax, xmin, xmax]):
            sub_area = (int(ymin), int(ymax), int(xmin), int(xmax))
        sd = SubtitleRemover(video_path, sub_area=sub_area)
        sd.run()
        output_path = sd.video_out_name
        oss_file_path = os.path.basename(output_path)
        result["output_video_url"] = upload_to_aliyun(output_path, oss_file_path)
    except Exception as e:
        print(f"error: {traceback.format_exc()}")
        result["status"] = -1
        result["message"] = f"error: {traceback.format_exc()}"
    return result


runpod.serverless.start({"handler": is_even})
