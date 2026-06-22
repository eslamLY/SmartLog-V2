"""
models/ml_performance.py — Model performance metrics tracking.
Stores live accuracy, precision, recall, F1 for each model.
"""

from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import json

from models import db
from models.predictions import ModelRegistry, ModelPerformanceLog, PredictionResult


class MLPerformanceTracker:

    @staticmethod
    def compute_daily_accuracy(model_key: str, target_date: Optional[date] = None) -> Dict:
        target_date = target_date or date.today()
        predictions = PredictionResult.query.filter(
            PredictionResult.prediction_date == target_date,
        ).all()
        if not predictions:
            return {'model_key': model_key, 'date': target_date.isoformat(), 'error': 'لا توجد تنبؤات'}
        total = len(predictions)
        correct = sum(1 for p in predictions if p.was_correct == True)
        incorrect = sum(1 for p in predictions if p.was_correct == False)
        pending = total - correct - incorrect
        accuracy = correct / max(total - pending, 1)
        positive = sum(1 for p in predictions if p.was_correct == True and p.risk_level in ('high', 'medium'))
        false_positive = sum(1 for p in predictions if p.was_correct == False and p.risk_level in ('high', 'medium'))
        false_negative = sum(1 for p in predictions if p.was_correct == False and p.risk_level == 'low')
        precision = positive / max(positive + false_positive, 1)
        recall = positive / max(positive + false_negative, 1)
        f1 = 2 * (precision * recall) / max(precision + recall, 0.001)
        entry = ModelPerformanceLog(
            model_key=model_key,
            prediction_date=target_date,
            total_predictions=total,
            correct_predictions=correct,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
        )
        db.session.add(entry)
        db.session.commit()
        return {
            'model_key': model_key,
            'date': target_date.isoformat(),
            'total_predictions': total,
            'correct': correct,
            'incorrect': incorrect,
            'pending': pending,
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
        }

    @staticmethod
    def record_outcome(prediction_id: int, actual_outcome: str) -> bool:
        pred = PredictionResult.query.get(prediction_id)
        if not pred:
            return False
        pred.actual_outcome = actual_outcome
        pred.was_correct = MLPerformanceTracker._evaluate_correctness(pred, actual_outcome)
        db.session.commit()
        return True

    @staticmethod
    def _evaluate_correctness(pred: PredictionResult, actual: str) -> bool:
        if pred.prediction_type == 'leave':
            return actual == 'on_leave' if pred.risk_level == 'high' else actual != 'on_leave'
        elif pred.prediction_type == 'absence':
            return actual == 'absent' if pred.risk_level == 'high' else actual != 'absent'
        elif pred.prediction_type == 'turnover':
            return actual == 'left' if pred.risk_level == 'high' else True
        return True

    @staticmethod
    def get_model_performance_summary(days: int = 30) -> List[Dict]:
        cutoff = date.today() - timedelta(days=days)
        logs = ModelPerformanceLog.query.filter(
            ModelPerformanceLog.prediction_date >= cutoff,
        ).order_by(ModelPerformanceLog.model_key, ModelPerformanceLog.prediction_date).all()
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.model_key].append(log)
        summary = []
        for model_key, entries in grouped.items():
            avg_acc = sum(e.accuracy for e in entries) / max(len(entries), 1)
            avg_prec = sum(e.precision for e in entries) / max(len(entries), 1)
            avg_rec = sum(e.recall for e in entries) / max(len(entries), 1)
            avg_f1 = sum(e.f1_score for e in entries) / max(len(entries), 1)
            total_preds = sum(e.total_predictions for e in entries)
            summary.append({
                'model_key': model_key,
                'avg_accuracy': round(avg_acc * 100, 1),
                'avg_precision': round(avg_prec * 100, 1),
                'avg_recall': round(avg_rec * 100, 1),
                'avg_f1': round(avg_f1 * 100, 1),
                'total_predictions': total_preds,
                'days_tracked': len(entries),
            })
        return summary

    @staticmethod
    def get_accuracy_trend(model_key: str, days: int = 90) -> List[Dict]:
        cutoff = date.today() - timedelta(days=days)
        entries = ModelPerformanceLog.query.filter(
            ModelPerformanceLog.model_key == model_key,
            ModelPerformanceLog.prediction_date >= cutoff,
        ).order_by(ModelPerformanceLog.prediction_date).all()
        return [{
            'date': e.prediction_date.isoformat(),
            'accuracy': round(e.accuracy * 100, 1),
            'precision': round(e.precision * 100, 1),
            'recall': round(e.recall * 100, 1),
            'f1': round(e.f1_score * 100, 1),
            'total': e.total_predictions,
        } for e in entries]

    @staticmethod
    def get_registered_models() -> List[Dict]:
        models = ModelRegistry.query.filter_by(is_active=True).all()
        return [{
            'id': m.id,
            'key': m.model_key,
            'type': m.model_type,
            'training_date': m.training_date.isoformat() if m.training_date else None,
            'metrics': json.loads(m.metrics_json) if m.metrics_json else {},
        } for m in models]

    @staticmethod
    def cleanup_old_logs(retain_days: int = 365):
        cutoff = date.today() - timedelta(days=retain_days)
        old = ModelPerformanceLog.query.filter(
            ModelPerformanceLog.prediction_date < cutoff
        ).all()
        count = len(old)
        for o in old:
            db.session.delete(o)
        db.session.commit()
        return count
