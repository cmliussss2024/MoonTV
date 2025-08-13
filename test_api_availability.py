import json
import requests
import concurrent.futures
from typing import Dict, Tuple, List
import time
import os

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_apis_from_config(config_path: str) -> Dict[str, dict]:
    """
    从配置文件中加载API列表
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config

def test_api(api_name: str, api_url: str, max_retries: int = 3) -> Tuple[str, str, bool, int]:
    """
    测试单个API的可用性
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            # 发送GET请求
            response = requests.get(
                api_url, 
                headers=headers, 
                timeout=10,
                verify=False  # 禁用SSL验证以避免证书问题
            )
            
            # 如果响应码为200，认为API可用
            if response.status_code == 200:
                return api_name, api_url, True, response.status_code
            
            # 如果不是最后一次尝试，等待一段时间再重试
            if attempt < max_retries - 1:
                time.sleep(1)
                
        except Exception as e:
            # 如果不是最后一次尝试，等待一段时间再重试
            if attempt < max_retries - 1:
                time.sleep(1)
            continue
    
    # 所有尝试都失败了
    return api_name, api_url, False, response.status_code if 'response' in locals() else -1

def remove_unavailable_apis(config: dict, unavailable_apis: List[str]) -> dict:
    """
    从配置中移除不可用的API
    """
    # 创建配置副本
    new_config = json.loads(json.dumps(config))
    
    # 移除不可用的API
    for api_name in unavailable_apis:
        if api_name in new_config.get('api_site', {}):
            del new_config['api_site'][api_name]
            print(f"已移除不可用的API: {api_name}")
    
    return new_config

def main():
    config_path = 'config.json'
    
    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        print(f"错误: 找不到配置文件 {config_path}")
        return
    
    # 从配置文件加载API列表
    config = load_apis_from_config(config_path)
    api_sites = config.get('api_site', {})
    
    apis = {}
    for key, value in api_sites.items():
        if 'api' in value:
            apis[key] = value['api']
    
    print(f"加载了 {len(apis)} 个API进行测试")
    print("=" * 80)
    
    # 存储结果
    results = []
    
    # 使用线程池并发测试所有API
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # 提交所有任务
        future_to_api = {
            executor.submit(test_api, name, url): (name, url) 
            for name, url in apis.items()
        }
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_api):
            name, url = future_to_api[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"测试 {name} 时发生错误: {e}")
                results.append((name, url, False, -1))
    
    # 分析结果
    available_count = sum(1 for r in results if r[2])
    unavailable_count = len(results) - available_count
    
    # 输出结果
    print("\n测试结果:")
    print("=" * 80)
    
    # 按可用性分组
    available_apis = [r for r in results if r[2]]
    unavailable_apis = [r for r in results if not r[2]]
    
    print(f"\n可用API ({available_count}个):")
    print("-" * 40)
    for name, url, available, status_code in available_apis:
        print(f"✓ {name}: {url} (状态码: {status_code})")
    
    print(f"\n不可用API ({unavailable_count}个):")
    print("-" * 40)
    for name, url, available, status_code in unavailable_apis:
        if status_code == -1:
            print(f"✗ {name}: {url} (请求失败)")
        else:
            print(f"✗ {name}: {url} (状态码: {status_code})")
    
    print(f"\n总结: {available_count}/{len(results)} 个API可用")
    
    # 询问是否移除不可用的API
    if unavailable_count > 0:
        choice = input(f"\n是否要从 {config_path} 中移除这 {unavailable_count} 个不可用的API? (y/N): ")
        if choice.lower() in ['y', 'yes']:
            # 获取不可用API的名称列表
            unavailable_api_names = [r[0] for r in unavailable_apis]
            
            # 移除不可用的API
            updated_config = remove_unavailable_apis(config, unavailable_api_names)
            
            # 备份原配置文件
            backup_path = f"{config_path}.backup"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"原配置已备份至: {backup_path}")
            
            # 保存更新后的配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(updated_config, f, ensure_ascii=False, indent=2)
            
            print(f"已从配置文件中移除 {unavailable_count} 个不可用的API")
        else:
            print("未执行移除操作")
    else:
        print("\n所有API均可用，无需清理")

if __name__ == "__main__":
    main()