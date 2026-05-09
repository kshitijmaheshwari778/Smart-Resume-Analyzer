import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from config.database import (
    get_database_connection, get_all_users, update_user_status, delete_user,
    get_all_jobs, add_job, update_job, update_job_status, delete_job,
    get_all_templates, add_template, update_template, delete_template
)
import io
import uuid
from plotly.subplots import make_subplots
from io import BytesIO

class DashboardManager:
    def __init__(self):
        self.db = get_database_connection()
        self.colors = {
            'primary': '#4CAF50',
            'secondary': '#2196F3',
            'warning': '#FFA726',
            'danger': '#F44336',
            'info': '#00BCD4',
            'success': '#66BB6A',
            'purple': '#9C27B0',
            'background': '#1E1E1E',
            'card': '#2D2D2D',
            'text': '#FFFFFF',
            'subtext': '#B0B0B0'
        }
        
    def apply_dashboard_style(self):
        """Apply custom styling for dashboard"""
        st.markdown("""
            <style>
                .dashboard-title {
                    font-size: 2.5rem;
                    font-weight: bold;
                    margin-bottom: 2rem;
                    color: white;
                    text-align: center;
                }
                
                .metric-card {
                    background-color: #2D2D2D;
                    border-radius: 15px;
                    padding: 1.5rem;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    transition: transform 0.3s ease;
                    height: 100%;
                }
                
                .metric-card:hover {
                    transform: translateY(-5px);
                }
                
                .metric-value {
                    font-size: 2.5rem;
                    font-weight: bold;
                    color: #4CAF50;
                    margin: 0.5rem 0;
                }
                
                .metric-label {
                    font-size: 1rem;
                    color: #B0B0B0;
                }
                
                .trend-up {
                    color: #4CAF50;
                    font-size: 1.2rem;
                }
                
                .trend-down {
                    color: #F44336;
                    font-size: 1.2rem;
                }
                
                .chart-container {
                    background-color: #2D2D2D;
                    border-radius: 15px;
                    padding: 1.5rem;
                    margin: 1rem 0;
                }
                
                .section-title {
                    font-size: 1.5rem;
                    color: white;
                    margin: 2rem 0 1rem 0;
                }
                
                .stPlotlyChart {
                    background-color: #2D2D2D;
                    border-radius: 15px;
                    padding: 1rem;
                }
                
                div[data-testid="stHorizontalBlock"] > div {
                    background-color: #2D2D2D;
                    border-radius: 15px;
                    padding: 1rem;
                    margin: 0.5rem;
                }

                [data-testid="stMetricValue"] {
                    font-size: 2rem !important;
                }

                [data-testid="stMetricLabel"] {
                    font-size: 1rem !important;
                }
            </style>
        """, unsafe_allow_html=True)

    def get_resume_metrics(self):
        """Get resume-related metrics from database"""
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_month = now.replace(day=1)
        
        metrics = {}
        for period, start_date in [
            ('Today', start_of_day),
            ('This Week', start_of_week),
            ('This Month', start_of_month),
            ('All Time', datetime(2000, 1, 1))
        ]:
            total = self.db.resume_data.count_documents({"created_at": {"$gte": start_date}})
            
            # Get resume IDs in this period
            resume_ids = [str(r['_id']) for r in self.db.resume_data.find({"created_at": {"$gte": start_date}}, {"_id": 1})]
            
            ats_score = 0
            keyword_score = 0
            high_scoring = 0
            if resume_ids:
                pipeline = [
                    {"$match": {"resume_id": {"$in": resume_ids}}},
                    {"$group": {
                        "_id": None,
                        "avg_ats": {"$avg": "$ats_score"},
                        "avg_kw": {"$avg": "$keyword_match_score"},
                        "high": {"$sum": {"$cond": [{"$gte": ["$ats_score", 70]}, 1, 0]}}
                    }}
                ]
                result = list(self.db.resume_analysis.aggregate(pipeline))
                if result:
                    ats_score = round(result[0].get('avg_ats', 0) or 0, 1)
                    keyword_score = round(result[0].get('avg_kw', 0) or 0, 1)
                    high_scoring = result[0].get('high', 0)
            
            metrics[period] = {'total': total, 'ats_score': ats_score, 'keyword_score': keyword_score, 'high_scoring': high_scoring}
        
        return metrics

    def get_skill_distribution(self):
        """Get skill distribution data"""
        categories_map = {'Programming': 0, 'Database': 0, 'Cloud': 0, 'Management': 0, 'Other': 0}
        
        for doc in self.db.resume_data.find({}, {"skills": 1}):
            skills_str = doc.get('skills', '')
            # Parse skills from string representation
            skills_str = skills_str.strip('[]').replace("'", "").replace('"', '')
            skills = [s.strip() for s in skills_str.split(',') if s.strip()]
            
            for skill in skills:
                sl = skill.lower()
                if any(k in sl for k in ['python', 'java', 'javascript', 'c++', 'programming']):
                    categories_map['Programming'] += 1
                elif any(k in sl for k in ['sql', 'database', 'mongodb']):
                    categories_map['Database'] += 1
                elif any(k in sl for k in ['aws', 'cloud', 'azure']):
                    categories_map['Cloud'] += 1
                elif any(k in sl for k in ['agile', 'scrum', 'management']):
                    categories_map['Management'] += 1
                else:
                    categories_map['Other'] += 1
        
        # Sort by count descending
        sorted_items = sorted(categories_map.items(), key=lambda x: x[1], reverse=True)
        categories = [item[0] for item in sorted_items if item[1] > 0]
        counts = [item[1] for item in sorted_items if item[1] > 0]
        return categories, counts

    def get_weekly_trends(self):
        """Get weekly submission trends"""
        now = datetime.now()
        dates = [(now - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(6, -1, -1)]
        
        submissions = []
        for date_str in dates:
            day_start = datetime.strptime(date_str, '%Y-%m-%d')
            day_end = day_start + timedelta(days=1)
            count = self.db.resume_data.count_documents({"created_at": {"$gte": day_start, "$lt": day_end}})
            submissions.append(count)
            
        return [d[-3:] for d in dates], submissions

    def get_job_category_stats(self):
        """Get statistics by job category"""
        pipeline = [
            {"$group": {"_id": {"$ifNull": ["$target_category", "Other"]}, "count": {"$sum": 1},
                        "resume_ids": {"$push": {"$toString": "$_id"}}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        results = list(self.db.resume_data.aggregate(pipeline))
        
        categories, success_rates = [], []
        for r in results:
            categories.append(r['_id'])
            # Calculate success rate for this category
            if r.get('resume_ids'):
                total_a = self.db.resume_analysis.count_documents({"resume_id": {"$in": r['resume_ids']}})
                high_a = self.db.resume_analysis.count_documents({"resume_id": {"$in": r['resume_ids']}, "ats_score": {"$gte": 70}})
                rate = round((high_a / total_a * 100), 1) if total_a > 0 else 0
            else:
                rate = 0
            success_rates.append(rate)
        return categories, success_rates

    def render_admin_panel(self):
        """Render admin panel with data management tools"""
        st.sidebar.markdown("### 👋 Welcome Admin!")
        st.sidebar.markdown("---")
        
        if st.sidebar.button("🚪 Logout"):
            st.session_state.is_admin = False
            st.rerun()
            
        st.sidebar.markdown("### 🛠️ Admin Tools")
        
        # Data Export Options
        export_format = st.sidebar.selectbox(
            "Export Format",
            ["Excel", "CSV", "JSON"],
            key="export_format"
        )
        
        if st.sidebar.button("📥 Export Data"):
            if export_format == "Excel":
                excel_data = self.export_to_excel()
                if excel_data:
                    st.sidebar.download_button(
                        "⬇️ Download Excel",
                        data=excel_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            elif export_format == "CSV":
                csv_data = self.export_to_csv()
                if csv_data:
                    st.sidebar.download_button(
                        "⬇️ Download CSV",
                        data=csv_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
            else:
                json_data = self.export_to_json()
                if json_data:
                    st.sidebar.download_button(
                        "⬇️ Download JSON",
                        data=json_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json"
                    )

        # Database Stats
        st.sidebar.markdown("### 📊 Database Stats")
        stats = self.get_database_stats()
        st.sidebar.markdown(f"""
            - Total Resumes: {stats['total_resumes']}
            - Today's Submissions: {stats['today_submissions']}
            - Storage Used: {stats['storage_size']}
        """)

    def get_resume_data(self):
        """Get all resume data"""
        try:
            resumes = list(self.db.resume_data.find().sort("created_at", -1))
            result = []
            for r in resumes:
                rid = str(r['_id'])
                a = self.db.resume_analysis.find_one({"resume_id": rid})
                result.append((
                    rid, r.get('name',''), r.get('email',''), r.get('phone',''),
                    r.get('linkedin',''), r.get('github',''), r.get('portfolio',''),
                    r.get('target_role',''), r.get('target_category',''),
                    str(r.get('created_at','')),
                    a.get('ats_score') if a else None,
                    a.get('keyword_match_score') if a else None,
                    a.get('format_score') if a else None,
                    a.get('section_score') if a else None
                ))
            return result
        except Exception as e:
            print(f"Error fetching resume data: {str(e)}")
            return []

    def render_resume_data_section(self):
        """Render resume data section with Excel download"""
        st.markdown("<h2 class='section-title'>Resume Submissions</h2>", unsafe_allow_html=True)
        
        # Get resume data
        resume_data = self.get_resume_data()
        
        if resume_data:
            # Convert to DataFrame
            columns = [
                'ID', 'Name', 'Email', 'Phone', 'LinkedIn', 'GitHub', 
                'Portfolio', 'Target Role', 'Target Category', 'Submission Date',
                'ATS Score', 'Keyword Match', 'Format Score', 'Section Score'
            ]
            df = pd.DataFrame(resume_data, columns=columns)
            
            # Format scores as percentages
            score_columns = ['ATS Score', 'Keyword Match', 'Format Score', 'Section Score']
            for col in score_columns:
                df[col] = df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
            
            # Style the dataframe
            st.markdown("""
            <style>
            .resume-data {
                background-color: #2D2D2D;
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="resume-data">', unsafe_allow_html=True)
                
                # Add filters
                col1, col2 = st.columns(2)
                with col1:
                    target_role = st.selectbox(
                        "Filter by Target Role",
                        options=["All"] + list(df['Target Role'].unique()),
                        key="role_filter"
                    )
                with col2:
                    target_category = st.selectbox(
                        "Filter by Category",
                        options=["All"] + list(df['Target Category'].unique()),
                        key="category_filter"
                    )
                
                # Apply filters
                filtered_df = df.copy()
                if target_role != "All":
                    filtered_df = filtered_df[filtered_df['Target Role'] == target_role]
                if target_category != "All":
                    filtered_df = filtered_df[filtered_df['Target Category'] == target_category]
                
                # Display filtered data
                st.dataframe(
                    filtered_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Add download buttons
                col1, col2 = st.columns(2)
                with col1:
                    # Download filtered data
                    excel_buffer = BytesIO()
                    filtered_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Filtered Data",
                        data=excel_buffer,
                        file_name=f"resume_data_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_filtered_data"
                    )
                
                with col2:
                    # Download all data
                    excel_buffer_all = BytesIO()
                    df.to_excel(excel_buffer_all, index=False, engine='openpyxl')
                    excel_buffer_all.seek(0)
                    
                    st.download_button(
                        label="📥 Download All Data",
                        data=excel_buffer_all,
                        file_name=f"resume_data_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_all_data"
                    )
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No resume submissions available")

    def render_admin_logs_section(self):
        # Get admin logs
        admin_logs = self.get_admin_logs()
        
        if admin_logs:
            # Convert to DataFrame
            df = pd.DataFrame(admin_logs, columns=['Admin Email', 'Action', 'Timestamp'])
            
            # Style the dataframe
            st.markdown("""
            <style>
            .admin-logs {
                background-color: #2D2D2D;
                border-radius: 10px;
                padding: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="admin-logs">', unsafe_allow_html=True)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Add download button
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Admin Logs as Excel",
                    data=excel_buffer,
                    file_name=f"admin_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_admin_logs"
                )
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No admin activity logs available")

    def render_admin_section(self):
        """Render admin section with tabs for various modules"""
        st.markdown("<h2 class='section-title'>Admin Management</h2>", unsafe_allow_html=True)
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Resume Submissions", "User Management", "Job Management", "Resume Templates", "Admin Logs"
        ])
        
        with tab1:
            self.render_resume_data_section()
        
        with tab2:
            self.render_user_management_section()
            
        with tab3:
            self.render_job_management_section()
            
        with tab4:
            self.render_template_management_section()

        with tab5:
            self.render_admin_logs_section()

    def render_user_management_section(self):
        st.markdown("### User Management")
        users = get_all_users()
        if not users:
            st.info("No users found.")
            return

        df = pd.DataFrame(users)
        st.dataframe(df[['name', 'email', 'status', 'role', 'created_at']], use_container_width=True, hide_index=True)

        st.markdown("#### User Actions")
        col1, col2 = st.columns(2)
        with col1:
            user_to_update = st.selectbox("Select User to Update Status", options=users, format_func=lambda x: f"{x['name']} ({x['email']})")
            new_status = st.selectbox("New Status", ["Active", "Blocked"])
            if st.button("Update Status"):
                if update_user_status(user_to_update['id'], new_status):
                    st.success(f"User {user_to_update['email']} status updated to {new_status}")
                    st.rerun()
                else:
                    st.error("Failed to update user status")
        with col2:
            user_to_delete = st.selectbox("Select User to Delete", options=users, format_func=lambda x: f"{x['name']} ({x['email']})", key="del_user")
            if st.button("Delete User", type="primary"):
                if delete_user(user_to_delete['id']):
                    st.success(f"User {user_to_delete['email']} deleted")
                    st.rerun()
                else:
                    st.error("Failed to delete user")

    def render_job_management_section(self):
        st.markdown("### Job Management")
        
        # Add new job
        with st.expander("➕ Add New Job"):
            with st.form("add_job_form"):
                j_title = st.text_input("Job Title")
                j_company = st.text_input("Company")
                j_location = st.text_input("Location")
                j_desc = st.text_area("Description")
                j_status = st.selectbox("Status", ["Active", "Inactive", "Pending"])
                if st.form_submit_button("Create Job"):
                    if j_title and j_company:
                        job_data = {"title": j_title, "company": j_company, "location": j_location, "description": j_desc, "status": j_status}
                        if add_job(job_data):
                            st.success("Job created successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to create job.")
                    else:
                        st.error("Title and Company are required.")

        # List jobs
        jobs = get_all_jobs()
        if jobs:
            df = pd.DataFrame(jobs)
            st.dataframe(df[['title', 'company', 'location', 'status', 'created_at']], use_container_width=True, hide_index=True)
            
            st.markdown("#### Job Actions")
            col1, col2 = st.columns(2)
            with col1:
                job_to_update = st.selectbox("Select Job to Update", options=jobs, format_func=lambda x: f"{x['title']} at {x['company']}")
                new_j_status = st.selectbox("Update Status", ["Active", "Inactive", "Pending"], key="j_status")
                if st.button("Update Job Status"):
                    if update_job_status(job_to_update['_id'], new_j_status):
                        st.success("Job status updated!")
                        st.rerun()
                    else:
                        st.error("Failed to update job status")
            with col2:
                job_to_delete = st.selectbox("Select Job to Delete", options=jobs, format_func=lambda x: f"{x['title']} at {x['company']}", key="del_job")
                if st.button("Delete Job", type="primary"):
                    if delete_job(job_to_delete['_id']):
                        st.success("Job deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete job")
        else:
            st.info("No jobs posted yet.")

    def render_template_management_section(self):
        st.markdown("### Resume Templates Management")

        # Add new template
        with st.expander("➕ Add New Template"):
            with st.form("add_template_form"):
                t_name = st.text_input("Template Name")
                t_desc = st.text_area("Description")
                t_file = st.file_uploader("Upload Template File (e.g., DOCX, PDF)", type=["docx", "pdf"])
                if st.form_submit_button("Upload Template"):
                    if t_name and t_file:
                        # Convert file to base64 for MongoDB storage
                        import base64
                        file_b64 = base64.b64encode(t_file.read()).decode('utf-8')
                        temp_data = {"name": t_name, "description": t_desc, "filename": t_file.name, "file_data": file_b64}
                        if add_template(temp_data):
                            st.success("Template added successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to add template.")
                    else:
                        st.error("Template Name and File are required.")

        # List templates
        templates = get_all_templates()
        if templates:
            df = pd.DataFrame(templates)
            st.dataframe(df[['name', 'description', 'filename', 'created_at']], use_container_width=True, hide_index=True)
            
            st.markdown("#### Template Actions")
            temp_to_delete = st.selectbox("Select Template to Delete", options=templates, format_func=lambda x: x['name'])
            if st.button("Delete Template", type="primary"):
                if delete_template(temp_to_delete['_id']):
                    st.success("Template deleted!")
                    st.rerun()
                else:
                    st.error("Failed to delete template")
        else:
            st.info("No templates available.")

    def export_to_excel(self):
        """Export data to Excel format"""
        try:
            df = self._get_export_dataframe()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Resume Data', index=False)
                workbook = writer.book
                worksheet = writer.sheets['Resume Data']
                header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1})
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                for i, col in enumerate(df.columns):
                    max_length = max(df[col].astype(str).apply(len).max(), len(str(col))) + 2
                    worksheet.set_column(i, i, min(max_length, 50))
            output.seek(0)
            return output.getvalue()
        except Exception as e:
            st.error(f"Error exporting to Excel: {str(e)}")
            return None

    def export_to_csv(self):
        """Export data to CSV format"""
        try:
            df = self._get_export_dataframe()
            return df.to_csv(index=False).encode('utf-8')
        except Exception as e:
            st.error(f"Error exporting to CSV: {str(e)}")
            return None

    def export_to_json(self):
        """Export data to JSON format"""
        try:
            df = self._get_export_dataframe()
            return df.to_json(orient='records', date_format='iso')
        except Exception as e:
            st.error(f"Error exporting to JSON: {str(e)}")
            return None

    def _get_export_dataframe(self):
        """Helper to build export dataframe from MongoDB"""
        resumes = list(self.db.resume_data.find().sort("created_at", -1))
        rows = []
        for r in resumes:
            rid = str(r['_id'])
            a = self.db.resume_analysis.find_one({"resume_id": rid}) or {}
            rows.append({
                'name': r.get('name',''), 'email': r.get('email',''), 'phone': r.get('phone',''),
                'linkedin': r.get('linkedin',''), 'github': r.get('github',''), 'portfolio': r.get('portfolio',''),
                'summary': r.get('summary',''), 'target_role': r.get('target_role',''),
                'target_category': r.get('target_category',''), 'education': r.get('education',''),
                'experience': r.get('experience',''), 'projects': r.get('projects',''),
                'skills': r.get('skills',''), 'ats_score': a.get('ats_score'),
                'keyword_match_score': a.get('keyword_match_score'), 'format_score': a.get('format_score'),
                'section_score': a.get('section_score'), 'missing_skills': a.get('missing_skills'),
                'recommendations': a.get('recommendations'), 'created_at': str(r.get('created_at',''))
            })
        return pd.DataFrame(rows)

    def get_database_stats(self):
        """Get database statistics"""
        stats = {}
        stats['total_resumes'] = self.db.resume_data.count_documents({})
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats['today_submissions'] = self.db.resume_data.count_documents({"created_at": {"$gte": today_start}})
        try:
            db_stats = self.db.command('dbstats')
            size_bytes = db_stats.get('dataSize', 0)
        except Exception:
            size_bytes = 0
        if size_bytes < 1024:
            stats['storage_size'] = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            stats['storage_size'] = f"{size_bytes/1024:.1f} KB"
        else:
            stats['storage_size'] = f"{size_bytes/(1024*1024):.1f} MB"
        return stats

    def get_admin_logs(self):
        """Get admin logs"""
        try:
            logs = list(self.db.admin_logs.find({}, {"_id": 0}).sort("timestamp", -1))
            return [(l.get('admin_email',''), l.get('action',''), str(l.get('timestamp',''))) for l in logs]
        except Exception as e:
            print(f"Error fetching admin logs: {str(e)}")
            return []

    def render_dashboard(self):
        """Main dashboard rendering function"""
        # Apply styling
        st.markdown("""
            <style>
                .dashboard-container {
                    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                    padding: 2rem;
                    border-radius: 20px;
                    margin: -1rem -1rem 2rem -1rem;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                }
                .dashboard-title {
                    color: #4FD1C5;
                    font-size: 2.5rem;
                    margin-bottom: 0.5rem;
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }
                .dashboard-icon {
                    background: rgba(79, 209, 197, 0.2);
                    padding: 0.5rem;
                    border-radius: 12px;
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 1.5rem;
                    margin-top: 2rem;
                }
                .stat-card {
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(10px);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    transition: all 0.3s ease;
                }
                .stat-card:hover {
                    transform: translateY(-5px);
                    background: rgba(255, 255, 255, 0.1);
                }
                .stat-value {
                    font-size: 2.5rem;
                    font-weight: bold;
                    margin: 0;
                    color: #4FD1C5;
                }
                .stat-label {
                    font-size: 1rem;
                    color: rgba(255, 255, 255, 0.7);
                    margin: 0.5rem 0 0 0;
                }
                .section-title {
                    color: #4FD1C5;
                    font-size: 1.5rem;
                    margin: 1rem 0 0.5rem 0;
                    padding-bottom: 0.5rem;
                    border-bottom: 2px solid rgba(79, 209, 197, 0.2);
                }
                .chart-container {
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    padding: 1rem;
                    margin-bottom: 1rem;
                }
                .insights-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 1.5rem;
                    margin-top: 1rem;
                }
                .insight-card {
                    background: rgba(255, 255, 255, 0.05);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                .trend-indicator {
                    display: inline-flex;
                    align-items: center;
                    padding: 0.25rem 0.5rem;
                    border-radius: 12px;
                    font-size: 0.875rem;
                    margin-left: 0.5rem;
                }
                .trend-up {
                    background: rgba(46, 204, 113, 0.2);
                    color: #2ecc71;
                }
                .trend-down {
                    background: rgba(231, 76, 60, 0.2);
                    color: #e74c3c;
                }
                @keyframes fadeInUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                .animate-fade-in {
                    animation: fadeInUp 0.5s ease-out forwards;
                }
            </style>
        """, unsafe_allow_html=True)

        # Dashboard Header
        st.markdown("""
            <div class="dashboard-container animate-fade-in">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="dashboard-title">
                        <span class="dashboard-icon">📊</span>
                        Resume Analytics Dashboard
                    </div>
                    <div style="color: rgba(255, 255, 255, 0.7);">
                        Last updated: {}
                    </div>
                </div>
            """.format(datetime.now().strftime('%B %d, %Y %I:%M %p')), unsafe_allow_html=True)

        # Quick Stats
        stats = self.get_quick_stats()
        trend_indicators = self.get_trend_indicators()
        
        st.markdown("""
            <div class="stats-grid">
                <div class="stat-card">
                    <p class="stat-value">{}</p>
                    <p class="stat-label">Total Resumes</p>
                    <span class="trend-indicator {}">
                        {} {}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{}</p>
                    <p class="stat-label">Avg ATS Score</p>
                    <span class="trend-indicator {}">
                        {} {}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{}</p>
                    <p class="stat-label">High Performing</p>
                    <span class="trend-indicator {}">
                        {} {}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{}</p>
                    <p class="stat-label">Success Rate</p>
                    <span class="trend-indicator {}">
                        {} {}%
                    </span>
                </div>
            </div>
            </div>
        """.format(
            stats['Total Resumes'], 
            trend_indicators['resumes']['class'], trend_indicators['resumes']['icon'], trend_indicators['resumes']['value'],
            stats['Avg ATS Score'],
            trend_indicators['ats']['class'], trend_indicators['ats']['icon'], trend_indicators['ats']['value'],
            stats['High Performing'],
            trend_indicators['high_performing']['class'], trend_indicators['high_performing']['icon'], trend_indicators['high_performing']['value'],
            stats['Success Rate'],
            trend_indicators['success_rate']['class'], trend_indicators['success_rate']['icon'], trend_indicators['success_rate']['value']
        ), unsafe_allow_html=True)

        # Performance Analytics Section
        st.markdown('<div class="section-title">📈 Performance Analytics</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_enhanced_ats_gauge(float(stats['Avg ATS Score'].rstrip('%')))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_skill_distribution_chart()
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Additional Analytics
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_submission_trends_chart()
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_job_category_chart()
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Key Insights Section
        st.markdown('<div class="section-title">🎯 Key Insights</div>', unsafe_allow_html=True)
        insights = self.get_detailed_insights()
        
        st.markdown('<div class="insights-grid">', unsafe_allow_html=True)
        for insight in insights:
            st.markdown(f"""
                <div class="insight-card">
                    <h3 style="color: #4FD1C5; margin-bottom: 1rem;">
                        {insight['icon']} {insight['title']}
                    </h3>
                    <p style="color: rgba(255, 255, 255, 0.7); margin: 0;">
                        {insight['description']}
                    </p>
                    <div style="margin-top: 1rem;">
                        <span class="trend-indicator {insight['trend_class']}">
                            {insight['trend_icon']} {insight['trend_value']}
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Admin logs section with Excel download functionality
        if st.session_state.get('is_admin', False):
            self.render_admin_section()

    def get_trend_indicators(self):
        """Get trend indicators for stats"""
        indicators = {}
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        for metric in ['resumes', 'ats', 'high_performing', 'success_rate']:
            try:
                if metric == 'resumes':
                    total_now = self.db.resume_data.count_documents({})
                    total_old = self.db.resume_data.count_documents({"created_at": {"$lt": seven_days_ago}})
                    change = ((total_now - total_old) * 100.0 / total_old) if total_old > 0 else 0
                elif metric == 'ats':
                    p1 = list(self.db.resume_analysis.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$ats_score"}}}]))
                    p2 = list(self.db.resume_analysis.aggregate([{"$match": {"created_at": {"$lt": seven_days_ago}}}, {"$group": {"_id": None, "avg": {"$avg": "$ats_score"}}}]))
                    avg_now = p1[0]['avg'] if p1 and p1[0].get('avg') else 0
                    avg_old = p2[0]['avg'] if p2 and p2[0].get('avg') else 0
                    change = ((avg_now - avg_old) * 100.0 / avg_old) if avg_old > 0 else 0
                else:
                    change = 0
                
                indicators[metric] = {
                    'value': abs(round(change, 1)),
                    'icon': '↑' if change >= 0 else '↓',
                    'class': 'trend-up' if change >= 0 else 'trend-down'
                }
            except Exception:
                indicators[metric] = {'value': 0, 'icon': '→', 'class': 'trend-neutral'}
        
        return indicators

    def get_detailed_insights(self):
        """Get detailed insights from the database"""
        insights = []
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Top performing category - find categories with best avg ATS scores
        try:
            categories = {}
            for r in self.db.resume_data.find({}, {"_id": 1, "target_category": 1}):
                cat = r.get('target_category', 'Other') or 'Other'
                rid = str(r['_id'])
                a = self.db.resume_analysis.find_one({"resume_id": rid})
                if a and a.get('ats_score') is not None:
                    categories.setdefault(cat, []).append(a['ats_score'])
            
            if categories:
                best = max(categories.items(), key=lambda x: sum(x[1])/len(x[1]))
                avg_s = sum(best[1]) / len(best[1])
                insights.append({'title': 'Top Performing Category', 'icon': '🏆',
                    'description': f"{best[0]} leads with {avg_s:.1f}% average ATS score across {len(best[1])} submissions",
                    'trend_class': 'trend-up', 'trend_icon': '↑', 'trend_value': f"{avg_s:.1f}%"})
        except Exception:
            pass
        
        # Weekly trend
        try:
            p_recent = list(self.db.resume_analysis.aggregate([{"$match": {"created_at": {"$gte": seven_days_ago}}}, {"$group": {"_id": None, "avg": {"$avg": "$ats_score"}}}]))
            p_old = list(self.db.resume_analysis.aggregate([{"$match": {"created_at": {"$lt": seven_days_ago}}}, {"$group": {"_id": None, "avg": {"$avg": "$ats_score"}}}]))
            recent_s = p_recent[0]['avg'] if p_recent and p_recent[0].get('avg') else None
            old_s = p_old[0]['avg'] if p_old and p_old[0].get('avg') else None
            if recent_s is not None and old_s is not None:
                change = recent_s - old_s
                insights.append({'title': 'Weekly Trend', 'icon': '📈',
                    'description': f"ATS scores have {'improved' if change >= 0 else 'decreased'} by {abs(change):.1f}% in the last week",
                    'trend_class': 'trend-up' if change >= 0 else 'trend-down',
                    'trend_icon': '↑' if change >= 0 else '↓', 'trend_value': f"{abs(change):.1f}%"})
        except Exception:
            pass
        
        # Top skills
        try:
            skill_counts = {}
            for doc in self.db.resume_data.find({"skills": {"$ne": None}}, {"skills": 1}):
                skills_str = doc.get('skills', '').strip('[]').replace("'", "").replace('"', '')
                for s in skills_str.split(','):
                    s = s.strip()
                    if s:
                        skill_counts[s] = skill_counts.get(s, 0) + 1
            top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_skills:
                parts = [f"{s[0]} ({s[1]} resumes)" for s in top_skills]
                insights.append({'title': 'Top Skills', 'icon': '💡',
                    'description': f"Most in-demand skills: {', '.join(parts)}",
                    'trend_class': 'trend-up', 'trend_icon': '🔝', 'trend_value': f"Top {len(top_skills)}"})
        except Exception:
            pass
        
        return insights

    def get_quick_stats(self):
        """Get quick statistics for the dashboard"""
        total_resumes = self.db.resume_data.count_documents({})
        
        avg_pipeline = list(self.db.resume_analysis.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$ats_score"}}}]))
        avg_ats = avg_pipeline[0]['avg'] if avg_pipeline and avg_pipeline[0].get('avg') else 0
        
        high_performing = self.db.resume_analysis.count_documents({"ats_score": {"$gte": 70}})
        success_rate = (high_performing / total_resumes * 100) if total_resumes > 0 else 0
        
        return {
            "Total Resumes": f"{total_resumes:,}",
            "Avg ATS Score": f"{avg_ats:.1f}%",
            "High Performing": f"{high_performing:,}",
            "Success Rate": f"{success_rate:.1f}%"
        }

    def create_enhanced_ats_gauge(self, value):
        """Create an enhanced ATS score gauge chart"""
        reference = 70  # Target score
        delta = value - reference
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            delta={
                'reference': reference,
                'valueformat': '.1f',
                'increasing': {'color': '#2ecc71'},
                'decreasing': {'color': '#e74c3c'}
            },
            number={'font': {'size': 40, 'color': 'white'}},
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickcolor': 'white',
                    'tickfont': {'color': 'white'}
                },
                'bar': {'color': '#3498db'},
                'bgcolor': 'rgba(0,0,0,0)',
                'borderwidth': 2,
                'bordercolor': 'white',
                'steps': [
                    {'range': [0, 40], 'color': '#e74c3c'},
                    {'range': [40, 70], 'color': '#f1c40f'},
                    {'range': [70, 100], 'color': '#2ecc71'}
                ],
                'threshold': {
                    'line': {'color': 'white', 'width': 4},
                    'thickness': 0.75,
                    'value': reference
                }
            }
        ))
        
        fig.update_layout(
            title={
                'text': 'ATS Score Performance',
                'font': {'size': 24, 'color': 'white'},
                'y': 0.85
            },
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': 'white'},
            height=350,
            margin=dict(l=20, r=20, t=80, b=20)
        )
        
        return fig

    def create_skill_distribution_chart(self):
        """Create a skill distribution chart"""
        categories, counts = self.get_skill_distribution()
        
        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=counts,
                marker_color=self.colors['info'],
                text=counts,
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title={
                'text': 'Skill Distribution',
                'y':0.95,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            height=350,  
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color=self.colors['text']),
            margin=dict(l=40, r=40, t=60, b=40),
            xaxis=dict(
                showgrid=False,
                showline=True,
                linecolor='rgba(255,255,255,0.2)',
                tickfont=dict(size=12)
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                zeroline=False
            ),
            bargap=0.3
        )
        return fig

    def create_submission_trends_chart(self):
        """Create a weekly submission trend chart"""
        dates, submissions = self.get_weekly_trends()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=submissions,
            mode='lines+markers',
            line=dict(color=self.colors['info'], width=3),
            marker=dict(size=8, color=self.colors['info'])
        ))
        
        fig.update_layout(
            title="Weekly Submission Pattern",
            paper_bgcolor=self.colors['card'],
            plot_bgcolor=self.colors['card'],
            font={'color': self.colors['text']},
            height=300,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        fig.update_xaxes(title_text="Day of Week", color=self.colors['text'])
        fig.update_yaxes(title_text="Number of Submissions", color=self.colors['text'])
        
        return fig

    def create_job_category_chart(self):
        """Create a success rate by category chart"""
        categories, rates = self.get_job_category_stats()
        fig = go.Figure(go.Bar(
            x=categories,
            y=rates,
            marker_color=[self.colors['success'], self.colors['info'], 
                        self.colors['warning'], self.colors['purple'], 
                        self.colors['secondary']],
            text=[f"{rate}%" for rate in rates],
            textposition='auto',
        ))
        
        fig.update_layout(
            title="Success Rate by Job Category",
            paper_bgcolor=self.colors['card'],
            plot_bgcolor=self.colors['card'],
            font={'color': self.colors['text']},
            height=300,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        fig.update_xaxes(title_text="Job Category", color=self.colors['text'])
        fig.update_yaxes(title_text="Success Rate (%)", color=self.colors['text'])
        
        return fig