"""
Manual Task Testing Script
Run this to test your Celery tasks manually
"""

from app.workers.celery_tasks.task_management_tasks import (
    check_low_stock_and_create_tasks,
    create_monthly_salary_tasks,
    check_overdue_tasks_and_notify,
    check_tasks_due_soon,
    send_daily_task_digests,
    escalate_overdue_high_priority_tasks
)

def test_individual_tasks():
    """Test each task individually"""
    print("🚀 Starting Manual Task Testing...")
    
    # Test 1: Low Stock Check
    print("\n1️⃣ Testing Low Stock Check...")
    try:
        result = check_low_stock_and_create_tasks.delay()
        print(f"   ✅ Task sent! ID: {result.id}")
        print(f"   📊 Status: {result.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Overdue Tasks Check
    print("\n2️⃣ Testing Overdue Tasks Check...")
    try:
        result = check_overdue_tasks_and_notify.delay()
        print(f"   ✅ Task sent! ID: {result.id}")
        print(f"   📊 Status: {result.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Tasks Due Soon
    print("\n3️⃣ Testing Tasks Due Soon...")
    try:
        result = check_tasks_due_soon.delay()
        print(f"   ✅ Task sent! ID: {result.id}")
        print(f"   📊 Status: {result.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Monthly Salary Tasks
    print("\n4️⃣ Testing Monthly Salary Tasks...")
    try:
        result = create_monthly_salary_tasks.delay()
        print(f"   ✅ Task sent! ID: {result.id}")
        print(f"   📊 Status: {result.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎉 All tests completed! Check your Worker terminal and Flower UI for results.")

def check_task_result(task_id):
    """Check specific task result"""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    print(f"\n📋 Task ID: {task_id}")
    print(f"📊 Status: {result.status}")
    print(f"💾 Result: {result.result}")
    if result.failed():
        print(f"❌ Error: {result.traceback}")

def wait_and_check_results():
    """Wait for tasks and check results"""
    import time
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    print("\n⏳ Testing with result checking...")
    
    # Send a task
    result = check_low_stock_and_create_tasks.delay()
    print(f"🚀 Task sent: {result.id}")
    
    # Wait and check status
    for i in range(10):  # Check for 10 seconds
        status = result.status
        print(f"   Status ({i+1}s): {status}")
        
        if status in ['SUCCESS', 'FAILURE']:
            print(f"   ✅ Final Status: {status}")
            if status == 'SUCCESS':
                print(f"   💾 Result: {result.result}")
            else:
                print(f"   ❌ Error: {result.traceback}")
            break
        
        time.sleep(1)

if __name__ == "__main__":
    print("🧪 Celery Task Testing Menu")
    print("=" * 40)
    print("1. Test all tasks individually")
    print("2. Test with result monitoring")
    print("3. Check specific task result")
    
    choice = input("\nEnter your choice (1-3): ")
    
    if choice == "1":
        test_individual_tasks()
    elif choice == "2":
        wait_and_check_results()
    elif choice == "3":
        task_id = input("Enter task ID: ")
        check_task_result(task_id)
    else:
        print("Invalid choice. Running basic test...")
        test_individual_tasks()