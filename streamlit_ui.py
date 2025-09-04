import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, Any

# Configure page
st.set_page_config(
    page_title="Chamonix Ski Pass Automation",
    page_icon="🎿",
    layout="wide"
)

# Constants
API_BASE_URL = "http://localhost:5000"

def get_order_status(order_id: int) -> Dict[str, Any]:
    """Get order status from main application."""
    try:
        response = requests.get(f"{API_BASE_URL}/status/{order_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {'status': 'error', 'error': f'API error: {response.status_code}'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def retry_order(order_id: int) -> Dict[str, Any]:
    """Retry processing an order."""
    try:
        response = requests.post(f"{API_BASE_URL}/retry/{order_id}", timeout=10)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def get_health_status() -> Dict[str, Any]:
    """Get application health status."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {'status': 'error'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def main():
    st.title("🎿 Chamonix Ski Pass Automation Dashboard")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", [
        "Dashboard",
        "Order Status",
        "Manual Retry",
        "Test Order",
        "Logs"
    ])

    if page == "Dashboard":
        show_dashboard()
    elif page == "Order Status":
        show_order_status()
    elif page == "Manual Retry":
        show_manual_retry()
    elif page == "Test Order":
        show_test_order()
    elif page == "Logs":
        show_logs()

def show_dashboard():
    st.header("System Dashboard")

    # Health status
    col1, col2, col3, col4 = st.columns(4)

    health = get_health_status()

    with col1:
        status = health.get('status', 'unknown')
        color = "🟢" if status == 'healthy' else "🔴"
        st.metric("System Status", f"{color} {status.title()}")

    with col2:
        queue_size = health.get('queue_size', 0)
        st.metric("Queue Size", queue_size)

    with col3:
        processing_orders = health.get('processing_orders', 0)
        st.metric("Processing Orders", processing_orders)

    with col4:
        last_update = health.get('timestamp', 'Unknown')
        if last_update != 'Unknown':
            last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00')).strftime('%H:%M:%S')
        st.metric("Last Update", last_update)

    # Recent activity (placeholder)
    st.subheader("Recent Activity")

    # Sample data - in real implementation, this would come from the application
    activity_data = [
        {'Time': '14:30:22', 'Order ID': '12345', 'Status': 'Completed', 'Portal': 'CBM'},
        {'Time': '14:28:15', 'Order ID': '12344', 'Status': 'Failed', 'Portal': 'CBM'},
        {'Time': '14:25:08', 'Order ID': '12343', 'Status': 'Excluded', 'Portal': 'N/A'},
    ]

    df = pd.DataFrame(activity_data)
    st.dataframe(df, use_container_width=True)

    # Auto-refresh
    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

def show_order_status():
    st.header("Order Status Lookup")

    order_id = st.number_input("Enter Order ID", min_value=1, value=12345)

    if st.button("Get Status"):
        with st.spinner("Fetching order status..."):
            status = get_order_status(order_id)

            if status.get('status') == 'not_found':
                st.warning(f"Order {order_id} not found in system")
            elif status.get('status') == 'error':
                st.error(f"Error: {status.get('error', 'Unknown error')}")
            else:
                st.success("Order found!")

                # Display status information
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Order Information")
                    st.write(f"**Status:** {status.get('status', 'Unknown')}")

                    if 'started_at' in status:
                        st.write(f"**Started:** {status['started_at']}")

                    if 'completed_at' in status:
                        st.write(f"**Completed:** {status['completed_at']}")

                    if 'reason' in status:
                        st.write(f"**Reason:** {status['reason']}")

                    if 'error' in status:
                        st.error(f"**Error:** {status['error']}")

                with col2:
                    st.subheader("Order Data")
                    if 'order_data' in status:
                        st.json(status['order_data'])

                # Show voucher info if available
                if 'voucher_path' in status:
                    st.subheader("Voucher")
                    st.success(f"Voucher saved: {status['voucher_path']}")

def show_manual_retry():
    st.header("Manual Order Retry")

    st.info("Use this to manually retry failed or excluded orders")

    order_id = st.number_input("Order ID to Retry", min_value=1, value=12345)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Retry Order"):
            with st.spinner("Retrying order..."):
                result = retry_order(order_id)

                if 'error' in result:
                    st.error(f"Retry failed: {result['error']}")
                else:
                    st.success(f"Order {order_id} queued for retry")

    with col2:
        if st.button("📊 Check Status First"):
            status = get_order_status(order_id)
            if status.get('status') != 'not_found':
                st.json(status)
            else:
                st.warning("Order not found")

def show_test_order():
    st.header("Test Order Processing")

    st.warning("⚠️ This will create a test order in the system")

    # Load sample data
    try:
        with open('chx-phase1-sample.json', 'r') as f:
            sample_data = json.load(f)
    except FileNotFoundError:
        st.error("Sample order file not found")
        return

    # Display sample data
    st.subheader("Sample Order Data")
    edited_data = st.text_area(
        "Edit order data if needed:",
        value=json.dumps(sample_data, indent=2),
        height=400
    )

    if st.button("🧪 Submit Test Order"):
        try:
            order_data = json.loads(edited_data)

            # Send to webhook endpoint
            response = requests.post(
                f"{API_BASE_URL}/webhook/woocommerce",
                json=order_data,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                st.success("Test order submitted successfully!")
                st.json(response.json())
            else:
                st.error(f"Failed to submit test order: {response.status_code}")
                st.text(response.text)

        except json.JSONDecodeError:
            st.error("Invalid JSON data")
        except Exception as e:
            st.error(f"Error submitting test order: {e}")

def show_logs():
    st.header("Application Logs")

    log_file = "automation.log"

    if not os.path.exists(log_file):
        st.warning("Log file not found")
        return

    # Filter options
    col1, col2, col3 = st.columns(3)

    with col1:
        log_level = st.selectbox("Log Level", ["ALL", "INFO", "WARNING", "ERROR"])

    with col2:
        lines_to_show = st.number_input("Lines to Show", min_value=10, max_value=1000, value=100)

    with col3:
        if st.button("🔄 Refresh Logs"):
            st.rerun()

    # Read and display logs
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()

        # Filter by log level
        if log_level != "ALL":
            lines = [line for line in lines if log_level in line]

        # Show last N lines
        lines = lines[-lines_to_show:]

        # Display in text area
        log_content = ''.join(lines)
        st.text_area("Logs", value=log_content, height=600)

    except Exception as e:
        st.error(f"Error reading log file: {e}")

if __name__ == "__main__":
    main()

