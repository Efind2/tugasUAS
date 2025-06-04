from app import ma
from app.models.user import User
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema # <-- TAMBAHKAN INI

class UserSchema(SQLAlchemyAutoSchema): # <-- UBAH ma.SQLAlchemyAutoSchema menjadi SQLAlchemyAutoSchema
    class Meta:
        model = User
        load_only = ("password",)
        dump_only = ("id", "created_at", "updated_at", "role")

        exclude = ("password_hash",)

    password = ma.String(required=True, load_only=True)
    email = ma.String(required=True)
    name = ma.String(required=False)
    role = ma.String(dump_only=True)