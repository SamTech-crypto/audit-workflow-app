import streamlit as st
import pandas as pd
import smtplib
import datetime
import networkx as nx
import matplotlib.pyplot as plt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openpyxl import Workbook
from io import BytesIO
import base64
from graphviz import Digraph
from faker import Faker
import random
import re

# Configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'auditflow5@gmail.com',
    'sender_password': st.secrets.get('EMAIL_PASSWORD', '')
}

# Audit Task Management
class AuditWorkflow:
    def __init__(self):
        self.tasks = []
        self.task_graph = nx.DiGraph()
        self.faker = Faker()

    def validate_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def add_task(self, task_id, description, due_date, dependencies, assignee_email):
        try:
            if not task_id or task_id in [t['id'] for t in self.tasks]:
                raise ValueError("Task ID must be unique and non-empty")
            if not description:
                raise ValueError("Description cannot be empty")
            if not self.validate_email(assignee_email):
                raise ValueError("Invalid email format")
            due_date_obj = datetime.datetime.strptime(due_date, '%Y-%m-%d')
            if due_date_obj < datetime.datetime.now():
                raise ValueError("Due date cannot be in the past")
            task = {
                'id': task_id,
                'description': description,
                'due_date': due_date_obj,
                'dependencies': dependencies,
                'assignee_email': assignee_email,
                'status': 'Pending'
            }
            self.tasks.append(task)
            self.task_graph.add_node(task_id, label=description)
            for dep in dependencies:
                if dep not in [t['id'] for t in self.tasks[:-1]]:
                    raise ValueError(f"Dependency {dep} does not exist")
                self.task_graph.add_edge(dep, task_id)
            return True
        except ValueError as e:
            st.error(f"Error adding task: {str(e)}")
            return False
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            return False

    def generate_fake_tasks(self, num_tasks=5):
        try:
            task_ids = [f"T{i+1}" for i in range(len(self.tasks) + 1, len(self.tasks) + num_tasks + 1)]
            for i in range(num_tasks):
                task_id = task_ids[i]
                description = self.faker.sentence(nb_words=6)
                due_date = (datetime.datetime.now() + datetime.timedelta(days=random.randint(1, 10))).strftime('%Y-%m-%d')
                existing_ids = [t['id'] for t in self.tasks] + task_ids[:i]
                dependencies = random.sample(existing_ids, min(len(existing_ids), random.randint(0, 2)))
                assignee_email = self.faker.email()
                self.add_task(task_id, description, due_date, dependencies, assignee_email)
            return True
        except Exception as e:
            st.error(f"Error generating fake tasks: {str(e)}")
            return False

    def send_reminder(self, task):
        current_date = datetime.datetime.now()
        days_until_due = (task['due_date'] - current_date).days
        if days_until_due <= 2 and task['status'] == 'Pending':
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['sender_email']
            msg['To'] = task['assignee_email']
            msg['Subject'] = f"Audit Task Reminder: {task['description']}"
            body = f"""
            Dear Assignee,
            This is a reminder for your audit task:
            Task: {task['description']}
            Due Date: {task['due_date'].strftime('%Y-%m-%d')}
            Days Remaining: {days_until_due}
            Please complete this task or update its status.
            """
            msg.attach(MIMEText(body, 'plain'))
            try:
                with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
                    server.starttls()
                    server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
                    server.send_message(msg)
                return True
            except Exception as e:
                st.error(f"Failed to send email: {str(e)}")
                return False
        return False

    def generate_report(self):
        df = pd.DataFrame(self.tasks)
        if df.empty:
            st.warning("No tasks to generate report.")
            return None
        wb = Workbook()
        ws = wb.active
        ws.title = "Audit Workflow Report"
        headers = ['ID', 'Description', 'Due Date', 'Dependencies', 'Assignee Email', 'Status']
        for c, header in enumerate(headers, 1):
            ws.cell(row=1, column=c).value = header
        for r, row in enumerate(df.values, 2):
            for c, val in enumerate(row, 1):
                ws.cell(row=r, column=c).value = str(val)
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def visualize_workflow(self):
        if not self.task_graph.nodes:
            st.warning("No tasks to visualize.")
            return None
        dot = Digraph(comment='Audit Workflow')
        for node in self.task_graph.nodes():
            dot.node(node, self.task_graph.nodes[node]['label'])
        for edge in self.task_graph.edges():
            dot.edge(edge[0], edge[1])
        return dot

# Streamlit Interface
def main():
    st.title("Audit Workflow Automation System")
    if 'workflow' not in st.session_state:
        st.session_state.workflow = AuditWorkflow()
    workflow = st.session_state.workflow
    st.sidebar.header("Task Management")
    task_id = st.sidebar.text_input("Task ID")
    description = st.sidebar.text_input("Task Description")
    due_date = st.sidebar.text_input("Due Date (YYYY-MM-DD)")
    dependencies = st.sidebar.text_input("Dependencies (comma-separated Task IDs)")
    assignee_email = st.sidebar.text_input("Assignee Email")
    if st.sidebar.button("Add Task"):
        if task_id and description and due_date and assignee_email:
            dependencies_list = [dep.strip() for dep in dependencies.split(',')] if dependencies else []
            if workflow.add_task(task_id, description, due_date, dependencies_list, assignee_email):
                st.success("Task added successfully!")
        else:
            st.error("Please fill all required fields")
    if st.sidebar.button("Generate Fake Tasks"):
        if workflow.generate_fake_tasks():
            st.success("Generated 5 fake tasks!")
        else:
            st.error("Failed to generate fake tasks.")
    st.header("Current Tasks")
    if workflow.tasks:
        df = pd.DataFrame(workflow.tasks)
        st.dataframe(df)
        if st.button("Send Reminders"):
            reminders_sent = 0
            for task in workflow.tasks:
                if workflow.send_reminder(task):
                    reminders_sent += 1
            if reminders_sent > 0:
                st.success(f"Sent {reminders_sent} reminder(s) successfully!")
            else:
                st.info("No reminders needed at this time.")
        if st.button("Generate Report"):
            report = workflow.generate_report()
            if report:
                b64 = base64.b64encode(report.getvalue()).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="audit_report.xlsx">Download Report</a>'
                st.markdown(href, unsafe_allow_html=True)
        st.header("Workflow Visualization")
        dot = workflow.visualize_workflow()
        if dot:
            st.graphviz_chart(dot.source)
    else:
        st.info("No tasks added yet. Use the sidebar to add tasks.")

if __name__ == "__main__":
    main()