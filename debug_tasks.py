"""
Debug Celery Tasks - Check what's happening
"""

import time
from celery.result import AsyncResult
from app.core.celery_app import celery_app

def check_task_details(task_id):
    """Check detailed task information"""
    result = AsyncResult(task_id, app=celery_app)
    
    print(f"\n🔍 Task Details for: {task_id}")
    print(f"   Status: {result.status}")
    print(f"   Ready: {result.ready()}")
    print(f"   Successful: {result.successful()}")
    print(f"   Failed: {result.failed()}")
    
    if result.ready():
        if result.successful():
            print(f"   ✅ Result: {result.result}")
        else:
            print(f"   ❌ Error: {result.result}")
            print(f"   🔥 Traceback: {result.traceback}")
    
    # Check task info
    try:
        info = result.info
        print(f"   📋 Info: {info}")
    except:
        print(f"   📋 Info: Not available")

def test_simple_task():
    """Test with a simple task first"""
    print("🧪 Testing Simple Task...")
    
    # Create a simple test task
    from app.workers.celery_tasks.task_management_tasks import check_low_stock_and_create_tasks
    
    result = check_low_stock_and_create_tasks.delay()
    print(f"📤 Task sent: {result.id}")
    
    # Wait and monitor for 30 seconds
    for i in range(30):
        status = result.status
        print(f"   ⏱️  {i+1}s - Status: {status}")
        
        if status in ['SUCCESS', 'FAILURE', 'RETRY', 'REVOKED']:
            print(f"   🏁 Final Status: {status}")
            if status == 'SUCCESS':
                print(f"   ✅ Result: {result.result}")
            elif status == 'FAILURE':
                print(f"   ❌ Error: {result.result}")
                print(f"   🔥 Traceback: {result.traceback}")
            break
        
        time.sleep(1)
    
    return result.id

def check_worker_connection():
    """Check if worker is connected and active"""
    print("🔗 Checking Worker Connection...")
    
    # Check active workers
    inspect = celery_app.control.inspect()
    
    # Get active workers
    active_workers = inspect.active()
    if active_workers:
        print(f"   ✅ Active Workers: {list(active_workers.keys())}")
        for worker, tasks in active_workers.items():
            print(f"      {worker}: {len(tasks)} active tasks")
    else:
        print(f"   ❌ No active workers found!")
    
    # Get registered tasks
    registered = inspect.registered()
    if registered:
        for worker, tasks in registered.items():
            print(f"   📋 {worker} registered tasks: {len(tasks)}")
    
    # Check stats
    stats = inspect.stats()
    if stats:
        for worker, stat_info in stats.items():
            print(f"   📊 {worker} stats:")
            print(f"      Pool: {stat_info.get('pool', 'N/A')}")
            print(f"      Processes: {stat_info.get('pool', {}).get('processes', 'N/A')}")

def check_redis_connection():
    """Check Redis connection"""
    print("🔴 Checking Redis Connection...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Test connection
        r.ping()
        print("   ✅ Redis connection successful")
        
        # Check queue
        queue_length = r.llen('celery')
        print(f"   📦 Celery queue length: {queue_length}")
        
        # Check if there are any pending tasks
        if queue_length > 0:
            print("   ⚠️  There are pending tasks in queue!")
        
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")

if __name__ == "__main__":
    print("🚨 Celery Task Debugging")
    print("=" * 50)
    
    # Check connections first
    check_redis_connection()
    print("\n" + "="*50)
    check_worker_connection()
    print("\n" + "="*50)
    
    # Test a simple task
    task_id = test_simple_task()
    
    # Check the task details
    print("\n" + "="*50)
    check_task_details(task_id)
    
    print("\n🔧 If tasks are still PENDING:")
    print("   1. Check your Worker terminal for error messages")
    print("   2. Make sure your database is running")
    print("   3. Check if there are any import errors in tasks")
    print("   4. Verify your app.core.celery_app configuration")