import os, uuid
from datetime import datetime, UTC

from models import db, BrandingConfig
from utils.helpers import allowed_file
from utils.constants import ALLOWED_EXTENSIONS


class BrandingService:

    @staticmethod
    def get_or_create():
        cfg = BrandingConfig.query.first()
        if not cfg:
            cfg = BrandingConfig()
            db.session.add(cfg)
            db.session.commit()
        return cfg

    @staticmethod
    def update(data: dict):
        cfg = BrandingConfig.query.first()
        if not cfg:
            cfg = BrandingConfig()
            db.session.add(cfg)
        fields = [
            'tenant_name', 'primary_color', 'accent_color',
            'bg_color', 'card_color', 'custom_css'
        ]
        for k in fields:
            if k in data:
                setattr(cfg, k, data[k])
        if 'company_lat' in data:
            cfg.company_lat = float(data['company_lat'])
        if 'company_lng' in data:
            cfg.company_lng = float(data['company_lng'])
        if 'allowed_radius_meters' in data:
            cfg.allowed_radius_meters = int(data['allowed_radius_meters'])
        cfg.updated_at = datetime.now(UTC)
        db.session.commit()
        return cfg

    @staticmethod
    def upload_logo(file_storage, upload_folder: str):
        if not file_storage or not file_storage.filename or not allowed_file(file_storage.filename):
            return None
        ext = file_storage.filename.rsplit('.', 1)[1].lower()
        fname = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
        file_storage.save(os.path.join(upload_folder, fname))
        cfg = BrandingConfig.query.first()
        if not cfg:
            cfg = BrandingConfig()
            db.session.add(cfg)
        cfg.logo_url = f'/uploads/{fname}'
        db.session.commit()
        return cfg.logo_url

    @staticmethod
    def to_dict(cfg):
        if not cfg:
            return {'use_default': True}
        return {
            'tenant_name': cfg.tenant_name,
            'logo_url': cfg.logo_url,
            'primary_color': cfg.primary_color,
            'accent_color': cfg.accent_color,
            'bg_color': cfg.bg_color,
            'card_color': cfg.card_color,
            'company_lat': cfg.company_lat,
            'company_lng': cfg.company_lng,
            'allowed_radius_meters': cfg.allowed_radius_meters
        }
