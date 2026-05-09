"""
Utils Database module - MongoDB operations for resume and AI analysis
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
from config.database import get_database_connection
import json


class DatabaseManager:
    def __init__(self):
        self.db = get_database_connection()

    def save_resume(self, user_id, job_role, content):
        document = {
            'user_id': user_id,
            'job_role': job_role,
            'content': content,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = self.db.resumes.insert_one(document)
        return str(result.inserted_id)

    def get_resume(self, resume_id):
        return self.db.resumes.find_one({"_id": resume_id})

    def get_user_resumes(self, user_id):
        return list(self.db.resumes.find({"user_id": user_id}))

    def save_analysis(self, resume_id, analysis_data):
        document = {
            'resume_id': resume_id,
            'analysis_data': analysis_data,
            'created_at': datetime.utcnow()
        }
        result = self.db.analyses.insert_one(document)
        return str(result.inserted_id)

    def get_analysis(self, analysis_id):
        return self.db.analyses.find_one({"_id": analysis_id})

    def get_resume_analyses(self, resume_id):
        return list(self.db.analyses.find({"resume_id": resume_id}))

    def close(self):
        pass  # MongoDB client manages connections via connection pool


def save_resume_data(resume_data):
    """Save resume data to the database"""
    db = get_database_connection()
    try:
        resume_json = json.dumps(resume_data)
        document = {
            'user_id': 'anonymous',
            'job_role': resume_data.get('target_role', 'Unknown'),
            'content': resume_json,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = db.resumes.insert_one(document)
        return str(result.inserted_id)
    except Exception as e:
        raise e


def save_ai_analysis_data(resume_id, analysis_data):
    """Save AI analysis data to the database"""
    db = get_database_connection()
    try:
        document = {
            'resume_id': resume_id,
            'model_used': analysis_data.get('model_used', 'Unknown'),
            'resume_score': analysis_data.get('resume_score', 0),
            'job_role': analysis_data.get('job_role', 'Unknown'),
            'created_at': datetime.utcnow()
        }
        result = db.ai_analyses.insert_one(document)
        return str(result.inserted_id)
    except Exception as e:
        raise e


def get_ai_analysis_statistics():
    """Get statistics about AI analyses"""
    db = get_database_connection()
    try:
        total_analyses = db.ai_analyses.count_documents({})
        avg_pipeline = [{"$group": {"_id": None, "avg": {"$avg": "$resume_score"}}}]
        avg_result = list(db.ai_analyses.aggregate(avg_pipeline))
        average_score = float(avg_result[0]['avg']) if avg_result and avg_result[0].get('avg') else 0.0

        model_pipeline = [{"$group": {"_id": "$model_used", "count": {"$sum": 1}}}]
        model_usage = {r['_id']: r['count'] for r in db.ai_analyses.aggregate(model_pipeline)}

        role_pipeline = [{"$group": {"_id": "$job_role", "count": {"$sum": 1}}}]
        job_roles = {r['_id']: r['count'] for r in db.ai_analyses.aggregate(role_pipeline)}

        return {
            'total_analyses': total_analyses,
            'average_score': average_score,
            'model_usage': model_usage,
            'job_roles': job_roles
        }
    except Exception as e:
        print(f"Error getting AI analysis statistics: {e}")
        return None