from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

_fernet_instance = None

def get_fernet():
    return _fernet_instance

def set_fernet(f):
    global _fernet_instance
    _fernet_instance = f

from models.employee import Employee, Branch
from models.attendance import AttendanceLog, AttendancePolicy
from models.misc import LeaveRequest, OutingRequest, GPSLog, BrandingConfig, EmployeeDocument
from models.biotime_device import BioTimeDevice, DeviceEventLog, DeviceHealthSnapshot
from models.security import LoginAttempt, BiometricCredential, TrustedDevice, BlockedIP
from models.notifications import Notification
from models.shifts import ShiftType, ShiftSchedule, ShiftSwapRequest, ShiftCoverageRule, ShiftException
from models.admin import AuditLog, Role, Permission, EmployeePermission
from models.communications import EmailTemplate, EmailLog, SmsLog
from models.hrms import EmployeeProfile, LeaveBalance, SalarySlipArchive
from models.documents import DocumentReference, ArchivedDocument, DocumentAuditLog
from models.department import Department, DepartmentCertification, DepartmentAnnouncement, DepartmentTransfer
from models.anomaly import AttendanceAnomaly, EmployeePattern
from models.attendance_review import AttendanceReviewQueue
from models.payroll import PayrollRecord, SalaryComponent, DeductionRecord, SalaryAdvance, ApprovalWorkflow, ApprovalStep, PayrollAuditLog, BankPaymentDetail
from models.gps import GeofenceZone, GeofenceEvent, AlertLog, TrustedLocation, LocationAuditLog, TrackingPolicy, PhotoVerification
from models.backup import BackupMetadata, BackupSchedule, BackupAuditLog, BackupConfig, BackupRestoreLog
from models.rbac import RbacRole, RbacPermission, RbacEmployeeRole, RbacAuditLog, RbacPermissionRequest, RbacRoleTemplate, RbacDelegation
from models.predictions import ModelRegistry, ModelPerformanceLog, PredictionResult, CustomRule, HolidayCalendar, AnomalyLog, RiskAssessment
from models.ml_performance import MLPerformanceTracker
from models.employee_enhanced import (
    EmployeeExtended, EmployeeChild, EmployeeGrade,
    EmployeeQualification, EmployeeCertification,
    EmployeePromotion, PromotionEligibility,
    LeaveType, EmployeeLeaveBalance, EmployeeLeaveRequest,
    EmployeeDelegation, EmployeeTraining, EmployeePerformance,
    EmployeeDisciplinaryAction,
)

__all__ = [
    'db', 'get_fernet', 'set_fernet',
    'Employee', 'Department', 'DepartmentCertification', 'DepartmentAnnouncement', 'DepartmentTransfer', 'AttendanceAnomaly', 'EmployeePattern', 'ReportCorrection', 'ScheduledReport', 'AttendanceLog', 'AttendancePolicy',
    'LeaveRequest', 'OutingRequest', 'GPSLog',
    'BioTimeDevice', 'BrandingConfig', 'TrustedDevice',
    'BiometricCredential', 'Notification', 'EmployeeDocument',
    'AuditLog', 'Role', 'Permission', 'EmployeePermission',
    'EmailTemplate', 'EmailLog', 'SmsLog',
    'LoginAttempt', 'ShiftType', 'ShiftSchedule', 'ShiftSwapRequest', 'ShiftCoverageRule', 'ShiftException',
    'EmployeeProfile', 'LeaveBalance', 'SalarySlipArchive',
    'Branch', 'DocumentReference', 'ArchivedDocument', 'DocumentAuditLog',
    'DeviceEventLog', 'DeviceHealthSnapshot',
    'AttendanceReviewQueue',
    'PayrollRecord', 'SalaryComponent', 'DeductionRecord', 'SalaryAdvance', 'ApprovalWorkflow', 'ApprovalStep', 'PayrollAuditLog', 'BankPaymentDetail',
    'BackupMetadata', 'BackupSchedule', 'BackupAuditLog', 'BackupConfig', 'BackupRestoreLog',
    # Enhanced employee models
    'EmployeeExtended', 'EmployeeChild', 'EmployeeGrade',
    'EmployeeQualification', 'EmployeeCertification',
    'EmployeePromotion', 'PromotionEligibility',
    'LeaveType', 'EmployeeLeaveBalance', 'EmployeeLeaveRequest',
    'EmployeeDelegation', 'EmployeeTraining', 'EmployeePerformance',
    'EmployeeDisciplinaryAction',
]
