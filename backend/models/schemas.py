from __future__ import annotations
from enum import Enum
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(value: str) -> str:
    password = str(value or "")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    return password

class AgentStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class FindingSeverity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class AgentLog(BaseModel):
    name: str
    status: AgentStatus = AgentStatus.pending
    message: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

class CodeFileSummary(BaseModel):
    path: str
    lines: int
    functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)

class CodeAnalysisResult(BaseModel):
    files: list[CodeFileSummary] = Field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    languages: dict[str, int] = Field(default_factory=dict)

class SecurityFinding(BaseModel):
    file: str
    line: int = 0
    severity: FindingSeverity = FindingSeverity.medium
    context: str = "production"
    issue: str
    description: str = ""
    confidence: str = ""
    cwe: Optional[str] = None
    fingerprint: Optional[str] = None
    occurrences: int = 1
    remediation: str = ""
    evidence: str = ""
    category: str = "security"
    impact: str = ""
    false_positive_likelihood: str = "medium"
    affected_files: list[str] = Field(default_factory=list)

class QualityMetric(BaseModel):
    file: str
    context: str = "production"
    complexity: float = 0
    maintainability_index: float = 0
    issues: list[str] = Field(default_factory=list)
    smells: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    long_methods: int = 0
    large_classes: int = 0
    duplicate_blocks: int = 0
    dead_code_indicators: int = 0
    max_nesting_depth: int = 0
    too_many_parameters: int = 0
    quality_issues: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_blocks_detail: list[dict[str, Any]] = Field(default_factory=list)

class GeneratedTest(BaseModel):
    file: str
    target: str
    test_code: str
    rationale: str = ""
    test_type: str = "unit"
    confidence: str = "medium"
    needs_review: bool = False
    framework: Optional[str] = None
    target_kind: str = "source"
    assertion_strength: str = "medium"
    execution_safety: str = "safe"
    generated_test_category: str = "unit"
    execution_status: str = "not_executed"
    executed: bool = False
    passed: int = 0
    failed: int = 0

class CoverageResult(BaseModel):
    executed: bool = False
    passed: int = 0
    failed: int = 0
    coverage_percent: float = 0
    output: str = ""
    tool: str = ""
    estimated: bool = False
    reason: str = ""
    low_coverage_reasons: list[str] = Field(default_factory=list)
    uncovered_files: list[str] = Field(default_factory=list)

class Recommendation(BaseModel):
    title: str
    priority: FindingSeverity = FindingSeverity.medium
    description: str
    suggested_action: str
    category: str = "general"
    estimated_effort: str = "medium"
    business_impact: str = ""
    why: str = ""
    affected_files: list[str] = Field(default_factory=list)
    evidence: str = ""

class AnalysisReport(BaseModel):
    project_id: str
    project_name: str
    status: str
    quality_score: float
    security_score: float
    test_score: float
    overall_score: float
    code_analysis: CodeAnalysisResult
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    quality_metrics: list[QualityMetric] = Field(default_factory=list)
    generated_tests: list[GeneratedTest] = Field(default_factory=list)
    coverage: CoverageResult = Field(default_factory=CoverageResult)
    recommendations: list[Recommendation] = Field(default_factory=list)
    agent_logs: list[AgentLog] = Field(default_factory=list)
    report_json_url: Optional[str] = None
    report_pdf_url: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class GitHubAnalyzeRequest(BaseModel):
    url: str

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        return validate_email(value)

    @field_validator("password")
    @classmethod
    def password_must_be_valid(cls, value: str) -> str:
        return validate_password(value)

class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        return validate_email(value)

class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_valid(cls, value: str) -> str:
        return validate_password(value)

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    avatar_url: Optional[str] = Field(default=None, max_length=500)

class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        return validate_email(value)

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_valid(cls, value: str) -> str:
        return validate_password(value)

class MagicLinkRequest(BaseModel):
    email: str
    redirect_url: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        return validate_email(value)

class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict[str, Any]

class ProjectSummary(BaseModel):
    id: str
    name: str
    source_type: str
    source_url: Optional[str] = None
    filename: Optional[str] = None
    language: str = "Unknown"
    total_files: int = 0
    status: str = "queued"
    progress: int = 0
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
