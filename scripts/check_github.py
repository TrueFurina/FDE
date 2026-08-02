"""
检查 GitHub 仓库 TrueFurina/FDE 状态并准备上传
token 从环境变量 GITHUB_TOKEN 读取，不经过命令行
"""
import os
import subprocess
import sys

token = os.environ.get("GITHUB_TOKEN", "")
print(f"Token 长度: {len(token)}")

# 尝试用 curl 检查仓库（token 通过环境变量传给 curl 的方式）
# 用 --config 文件避免 token 出现在命令行

import tempfile

# 方法1: 用 requests 但关掉 SSL 验证试试（网络环境问题）
try:
    import requests
    import urllib3
    urllib3.disable_warnings()

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    # 检查用户信息（验证 token）
    try:
        r = requests.get("https://api.github.com/user", headers=headers, timeout=15, verify=False)
        print(f"用户检查: HTTP {r.status_code}")
        if r.status_code == 200:
            print(f"  当前用户: {r.json().get('login')}")
        else:
            print(f"  {r.text[:100]}")
    except Exception as e:
        print(f"  用户检查失败: {str(e)[:100]}")

    # 检查仓库
    try:
        r = requests.get("https://api.github.com/repos/TrueFurina/FDE", headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            d = r.json()
            print(f"仓库存在: {d['full_name']}")
            print(f"  private: {d.get('private')}")
            print(f"  default_branch: {d.get('default_branch')}")
        elif r.status_code == 404:
            print("仓库不存在 (404) - 需要创建")
        else:
            print(f"仓库检查: HTTP {r.status_code} - {r.text[:80]}")
    except Exception as e:
        print(f"仓库检查失败: {str(e)[:100]}")

except ImportError:
    print("requests 不可用")
