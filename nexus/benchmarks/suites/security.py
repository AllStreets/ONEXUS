"""
Security agent benchmark suite.
Tests Vex, Redline, Mandate, and Bastion accuracy.
"""
from __future__ import annotations

from nexus.benchmarks.models import BenchmarkCase, BenchmarkSuite

SECURITY_SUITE = BenchmarkSuite(
    name="Security Agents",
    description="Benchmark Vex, Bastion, Redline, and Mandate accuracy",
    cases=[
        # ----------------------------------------------------------------
        # Vex -- SQL injection detection
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="vex_sql_injection",
            module_name="vex",
            input_message='scan this: cursor.execute("SELECT * FROM users WHERE id = %s" % user_input)',
            expected_patterns=[r"(?i)sql.?inject", r"(?i)vulnerabilit|finding|issue|scan"],
        ),
        # Vex -- XSS detection
        BenchmarkCase(
            name="vex_xss_innerhtml",
            module_name="vex",
            input_message="scan: document.innerHTML = user_input",
            expected_patterns=[r"(?i)xss|cross.?site|innerHTML"],
        ),
        # Vex -- credential exposure
        BenchmarkCase(
            name="vex_credentials",
            module_name="vex",
            input_message='scan: password = "super_secret_123"',
            expected_patterns=[r"(?i)credential|secret|hardcoded"],
        ),
        # Vex -- eval injection
        BenchmarkCase(
            name="vex_eval",
            module_name="vex",
            input_message="scan: result = eval(user_data)",
            expected_patterns=[r"(?i)eval|inject|arbitrary"],
        ),
        # Vex -- pickle deserialization
        BenchmarkCase(
            name="vex_pickle",
            module_name="vex",
            input_message="scan: obj = pickle.load(open('data.pkl', 'rb'))",
            expected_patterns=[r"(?i)pickle|deserializ"],
        ),
        # Vex -- subprocess shell injection
        BenchmarkCase(
            name="vex_subprocess_shell",
            module_name="vex",
            input_message="scan: subprocess.call(cmd, shell=True)",
            expected_patterns=[r"(?i)shell|command.?inject|subprocess"],
        ),
        # Vex -- disabled TLS verification
        BenchmarkCase(
            name="vex_tls_disabled",
            module_name="vex",
            input_message="scan: requests.get(url, verify=False)",
            expected_patterns=[r"(?i)tls|ssl|verif"],
        ),
        # Vex -- weak hash function
        BenchmarkCase(
            name="vex_weak_hash",
            module_name="vex",
            input_message="scan: h = md5(data)",
            expected_patterns=[r"(?i)md5|sha1|weak|hash|crypto"],
        ),
        # Vex -- debug mode enabled
        BenchmarkCase(
            name="vex_debug_mode",
            module_name="vex",
            input_message="scan: DEBUG = True",
            expected_patterns=[r"(?i)debug|config"],
        ),
        # Vex -- safe code (no false positive)
        BenchmarkCase(
            name="vex_safe_code",
            module_name="vex",
            input_message="scan: x = 1 + 2",
            expected_patterns=[r"(?i)no.*(vulnerabilit|issue|finding)|clean"],
            unexpected_patterns=[r"(?i)critical", r"(?i)high.?risk"],
        ),

        # ----------------------------------------------------------------
        # Redline -- contract risk analysis
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="redline_unlimited_liability",
            module_name="redline",
            input_message="review: The contractor assumes unlimited liability for all damages arising from this agreement.",
            expected_patterns=[r"(?i)liabilit", r"(?i)risk|high"],
        ),
        BenchmarkCase(
            name="redline_auto_renewal",
            module_name="redline",
            input_message="review: This agreement shall auto-renew annually unless terminated with 5 days notice.",
            expected_patterns=[r"(?i)auto.?renew", r"(?i)risk|renewal"],
        ),
        BenchmarkCase(
            name="redline_ip_assignment",
            module_name="redline",
            input_message="review: All intellectual property created during engagement shall belong to the company.",
            expected_patterns=[r"(?i)ip|intellectual.?property", r"(?i)assign|ownership"],
        ),
        BenchmarkCase(
            name="redline_non_compete",
            module_name="redline",
            input_message="review: Employee agrees to a non-compete clause for 5 years after termination.",
            expected_patterns=[r"(?i)non.?compete", r"(?i)restrict|risk"],
        ),
        BenchmarkCase(
            name="redline_clean_contract",
            module_name="redline",
            input_message="review: This is a standard mutual agreement with limitation of liability and 30-day termination notice.",
            expected_patterns=[r"(?i)risk.?score|analysis"],
            unexpected_patterns=[r"(?i)critical"],
        ),

        # ----------------------------------------------------------------
        # Mandate -- compliance assessment
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="mandate_gdpr",
            module_name="mandate",
            input_message="assess GDPR compliance for a system that stores user email and name with consent-based processing",
            expected_patterns=[r"(?i)gdpr", r"(?i)compliance|assessment|control"],
        ),
        BenchmarkCase(
            name="mandate_hipaa",
            module_name="mandate",
            input_message="assess HIPAA compliance for a medical records system that handles patient health data",
            expected_patterns=[r"(?i)hipaa", r"(?i)compliance|control"],
        ),
        BenchmarkCase(
            name="mandate_soc2",
            module_name="mandate",
            input_message="assess SOC2 compliance for our cloud platform with access controls and monitoring",
            expected_patterns=[r"(?i)soc2", r"(?i)compliance|control"],
        ),
        BenchmarkCase(
            name="mandate_pci",
            module_name="mandate",
            input_message="assess PCI-DSS compliance for payment card processing system with encryption",
            expected_patterns=[r"(?i)pci", r"(?i)compliance|control"],
        ),
        BenchmarkCase(
            name="mandate_privacy_detection",
            module_name="mandate",
            input_message="evaluate privacy practices for a system that collects personal data with user consent",
            expected_patterns=[r"(?i)gdpr|privacy|compliance", r"(?i)control|assessment"],
        ),
    ],
)
