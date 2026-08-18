"""
Generates a 5,000-row synthetic VWO test-case corpus in a Jira-export-style CSV.

Deterministic (seeded) so the corpus is reproducible. Column names are chosen to
line up with the Advance RAG ingest CLI example in prompt.md:
    python ingest.py data/test_cases.csv --text-cols title,steps,expected,tags
                                          --meta-cols id,jira_id,priority,module
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

OUT_PATH = "vwo_test_cases.csv"
TOTAL_ROWS = 5000
PROJECT_KEY = "VWO"
KEY_START = 1001  # first Jira issue number, e.g. VWO-1001

# ---------------------------------------------------------------------------
# Domain data: VWO is a CRO / experimentation platform, so modules mirror its
# real product surface (A/B testing, personalization, analytics, etc.)
# ---------------------------------------------------------------------------

MODULES = [
    "A/B Testing", "Split URL Testing", "Multivariate Testing", "Personalization",
    "Feature Flags & Rollouts", "Server-Side Testing", "Web Heatmaps",
    "Session Recordings", "Form Analytics", "Funnels", "On-page Surveys",
    "Goals & Conversion Tracking", "Audience Segmentation", "SmartCode & SmartStats",
    "Dashboard & Reports", "Integrations", "Mobile App Testing (iOS/Android)",
    "API & SDK", "Team & Account Management", "Billing & Plans",
    "Notifications & Alerts", "Admin Settings & SSO", "Data Export & GDPR",
    "Widgets & On-site Campaigns",
]

# Per-module scenario "verbs" — the thing being tested. Combined later with
# generic action/assertion templates to build unique-ish test cases.
SCENARIOS = {
    "A/B Testing": [
        "creating a new A/B test with two variations", "editing a running test's traffic split",
        "pausing an active A/B test", "resuming a paused A/B test", "archiving a completed test",
        "cloning an existing test into a new campaign", "setting a primary conversion goal",
        "adding a secondary metric to a test", "previewing a variation before launch",
        "declaring a winner and rolling out the winning variation", "scheduling a test start/end date",
        "excluding a URL pattern from a running test", "targeting a test to a specific device type",
        "viewing statistical significance on the report page", "editing test name and description",
    ],
    "Split URL Testing": [
        "creating a split URL test between two live pages", "validating redirect URL syntax",
        "verifying traffic is split evenly across redirect variations",
        "excluding internal IP addresses from a split URL test",
        "checking that UTM parameters persist across the redirect",
        "pausing a split URL test mid-campaign",
    ],
    "Multivariate Testing": [
        "creating an MVT campaign with 3 sections and 2 variations each",
        "verifying the combination matrix generates correctly",
        "identifying the winning combination on the report",
        "excluding a low-traffic combination from a running MVT test",
        "adding a new section to a draft MVT campaign",
    ],
    "Personalization": [
        "creating a personalization campaign for a returning-visitor segment",
        "setting a geo-targeting rule for a personalization campaign",
        "previewing personalized content for a test visitor profile",
        "scheduling a personalization campaign for a holiday sale",
        "verifying fallback content shows for visitors outside all segments",
    ],
    "Feature Flags & Rollouts": [
        "creating a new feature flag", "toggling a feature flag on for 10% of traffic",
        "targeting a feature flag rollout to a specific user segment",
        "rolling back a feature flag after an incident",
        "verifying flag state changes propagate within the SLA",
    ],
    "Server-Side Testing": [
        "initializing the server-side SDK with a valid account ID",
        "fetching variation assignment via the server-side API",
        "tracking a conversion event from the backend",
        "verifying bucketing consistency across repeated calls for the same visitor ID",
        "handling an SDK timeout gracefully",
    ],
    "Web Heatmaps": [
        "generating a click heatmap for the homepage",
        "generating a scroll-depth heatmap for a landing page",
        "filtering a heatmap by device type",
        "filtering a heatmap by traffic source",
        "exporting a heatmap report as an image",
    ],
    "Session Recordings": [
        "recording a visitor session end-to-end",
        "filtering session recordings by rage-click events",
        "filtering session recordings by visitor country",
        "playing back a recorded session at 2x speed",
        "masking sensitive form fields in a recorded session",
    ],
    "Form Analytics": [
        "tracking field-level drop-off on a signup form",
        "measuring average time spent per form field",
        "identifying the highest-abandonment field on a checkout form",
        "excluding bot traffic from form analytics data",
    ],
    "Funnels": [
        "creating a 4-step conversion funnel", "reordering steps within an existing funnel",
        "viewing drop-off percentage between two funnel steps",
        "segmenting funnel data by campaign source",
        "exporting funnel data to CSV",
    ],
    "On-page Surveys": [
        "creating a single-question NPS survey", "targeting a survey to exit-intent visitors",
        "setting a survey display frequency cap",
        "viewing aggregated survey responses on the dashboard",
        "closing a survey after reaching a response quota",
    ],
    "Goals & Conversion Tracking": [
        "creating a pageview-based goal", "creating a custom event-based goal",
        "creating a revenue goal with a minimum order value",
        "verifying goal attribution when a visitor converts across two sessions",
        "editing an existing goal's target URL pattern",
    ],
    "Audience Segmentation": [
        "creating a segment based on UTM source", "creating a segment based on returning-visitor status",
        "combining two conditions with AND logic in a segment",
        "combining two conditions with OR logic in a segment",
        "previewing estimated segment size before saving",
    ],
    "SmartCode & SmartStats": [
        "installing SmartCode on a new domain", "verifying SmartCode loads before page render",
        "enabling SmartStats for faster statistical significance",
        "verifying Bayesian probability-to-beat-baseline updates live",
    ],
    "Dashboard & Reports": [
        "viewing the account-level test summary dashboard",
        "filtering the reports list by date range",
        "exporting a test report as a PDF",
        "sharing a report via a public link",
        "customizing which metrics appear on the report overview card",
    ],
    "Integrations": [
        "connecting a Google Analytics 4 integration", "connecting a Segment integration",
        "connecting a Shopify store for e-commerce tracking",
        "connecting a HubSpot integration for lead sync",
        "disconnecting an integration and verifying data sync stops",
        "re-authenticating an expired integration token",
    ],
    "Mobile App Testing (iOS/Android)": [
        "initializing the mobile SDK on iOS", "initializing the mobile SDK on Android",
        "running an A/B test on a native mobile screen",
        "verifying offline event queuing and later sync on the mobile SDK",
        "targeting a mobile test to a specific app version",
    ],
    "API & SDK": [
        "authenticating against the public REST API with an API key",
        "fetching test results via the API",
        "creating a campaign programmatically via the API",
        "handling a 429 rate-limit response from the API",
        "verifying API response schema matches documentation",
    ],
    "Team & Account Management": [
        "inviting a new team member with editor role",
        "changing an existing team member's role to viewer",
        "removing a team member from the account",
        "creating a new workspace within an account",
        "transferring account ownership to another admin",
    ],
    "Billing & Plans": [
        "upgrading from a trial to a paid plan", "downgrading a subscription plan",
        "updating the billing payment method",
        "viewing invoice history",
        "verifying usage-based overage charges are calculated correctly",
    ],
    "Notifications & Alerts": [
        "enabling email alerts for test completion",
        "configuring a Slack webhook for goal-hit notifications",
        "muting notifications for a specific campaign",
        "verifying an alert fires when a test reaches significance",
    ],
    "Admin Settings & SSO": [
        "configuring SAML-based SSO for the account",
        "enforcing two-factor authentication for all team members",
        "setting an IP allowlist for account access",
        "rotating the account's API key",
    ],
    "Data Export & GDPR": [
        "submitting a data deletion request for a visitor ID",
        "exporting raw visitor-level data for a date range",
        "verifying PII fields are excluded from a standard export",
        "confirming a GDPR erasure request completes within SLA",
    ],
    "Widgets & On-site Campaigns": [
        "creating an on-site announcement bar campaign",
        "scheduling a widget campaign around a promotion window",
        "targeting a widget to first-time visitors only",
        "verifying widget close behavior persists across page navigations",
    ],
}

TEST_TYPES = ["Functional", "UI", "API", "Regression", "Smoke", "Performance", "Security", "Negative", "Usability"]
PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
PRIORITY_WEIGHTS = [0.12, 0.28, 0.35, 0.18, 0.07]
STATUSES = ["To Do", "In Progress", "Done", "Blocked", "In Review"]
STATUS_WEIGHTS = [0.30, 0.15, 0.40, 0.05, 0.10]

BROWSERS = ["Chrome 126", "Firefox 128", "Safari 17", "Edge 126"]
DEVICES = ["Desktop 1920x1080", "iPhone 14 (Safari)", "Pixel 8 (Chrome)", "iPad Air (Safari)"]
REPORTERS = ["a.mehta", "s.kapoor", "j.rodriguez", "l.chen", "p.singh", "m.oconnor", "r.iyer", "t.nakamura"]
ASSIGNEES = REPORTERS + ["unassigned"]
LABEL_POOL = ["regression", "smoke", "critical-path", "sprint-ready", "flaky-candidate",
              "needs-automation", "customer-reported", "beta-feature", "cross-browser", "mobile"]

ACTION_TEMPLATES = [
    "Verify the behavior when {scenario}.",
    "Validate {scenario} works as expected for a logged-in account admin.",
    "Confirm {scenario} handles edge-case input without errors.",
    "Check {scenario} across supported browsers.",
    "Ensure {scenario} completes and the UI reflects the change immediately.",
    "Verify error handling when {scenario} is attempted with invalid data.",
    "Confirm {scenario} respects account-level permissions.",
]

PRECONDITION_TEMPLATES = [
    "User is logged into the VWO dashboard with {role} permissions.",
    "An active VWO account exists with at least one live website connected.",
    "SmartCode is installed and verified on the target domain.",
    "Test environment has at least {n} days of historical traffic data.",
    "User has {role} access to the {module} module.",
]

ROLES = ["Admin", "Editor", "Viewer", "Owner"]

STEP_ACTIONS = [
    "Log in to the VWO dashboard.",
    "Navigate to the {module} section from the left sidebar.",
    "Click 'Create New' and select the appropriate option.",
    "Fill in the required fields with valid test data.",
    "Click 'Save' or 'Next' to proceed.",
    "Configure the targeting/audience rules.",
    "Review the summary panel before confirming.",
    "Click 'Launch' / 'Confirm' to apply the change.",
    "Refresh the page and re-open the item to verify persistence.",
    "Check the relevant report or list view for the updated state.",
]

EXPECTED_TEMPLATES = [
    "The system saves the change and displays a success confirmation toast.",
    "The updated state is reflected immediately in the dashboard without requiring a manual refresh.",
    "An audit log entry is created capturing the user, action, and timestamp.",
    "The change is visible to other team members with appropriate access within {latency} of saving.",
    "A validation error is shown and no partial data is persisted.",
    "The relevant report updates to reflect the new configuration on the next data refresh cycle.",
]


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def build_row(idx: int, jira_num: int) -> dict:
    module = random.choice(MODULES)
    scenario = random.choice(SCENARIOS[module])
    action_template = random.choice(ACTION_TEMPLATES)
    title = action_template.format(scenario=scenario).rstrip(".")
    title = title[0].upper() + title[1:]

    role = random.choice(ROLES)
    precondition = random.choice(PRECONDITION_TEMPLATES).format(role=role, n=random.choice([7, 14, 30]), module=module)

    n_steps = random.randint(4, 7)
    chosen_steps = random.sample(STEP_ACTIONS, k=n_steps)
    steps = "\n".join(f"{i + 1}. {s.format(module=module)}" for i, s in enumerate(chosen_steps))

    test_data_bits = [
        f"Browser: {random.choice(BROWSERS)}",
        f"Device: {random.choice(DEVICES)}",
    ]
    if random.random() < 0.5:
        test_data_bits.append(f"Account plan: {random.choice(['Growth', 'Pro', 'Enterprise'])}")
    if random.random() < 0.3:
        test_data_bits.append(f"Traffic split: {random.choice(['50/50', '70/30', '33/33/34'])}")
    test_data = "; ".join(test_data_bits)

    expected = random.choice(EXPECTED_TEMPLATES).format(latency=random.choice(["a few seconds", "1 minute", "5 minutes"]))

    test_type = random.choice(TEST_TYPES)
    priority = weighted_choice(PRIORITIES, PRIORITY_WEIGHTS)
    status = weighted_choice(STATUSES, STATUS_WEIGHTS)

    n_labels = random.randint(1, 3)
    tags = ",".join(random.sample(LABEL_POOL, k=n_labels))

    reporter = random.choice(REPORTERS)
    assignee = random.choice(ASSIGNEES)

    created = datetime(2025, 1, 1) + timedelta(days=random.randint(0, 590), minutes=random.randint(0, 1440))
    updated = created + timedelta(days=random.randint(0, 30), minutes=random.randint(0, 1440))
    sprint = f"Sprint {1 + (created.toordinal() // 14) % 40}"

    epic_link = f"{PROJECT_KEY}-{100 + MODULES.index(module)}"

    return {
        "id": idx,
        "jira_id": f"{PROJECT_KEY}-{jira_num}",
        "issue_type": "Test",
        "module": module,
        "epic_link": epic_link,
        "title": title,
        "priority": priority,
        "status": status,
        "test_type": test_type,
        "preconditions": precondition,
        "steps": steps,
        "test_data": test_data,
        "expected": expected,
        "tags": tags,
        "reporter": reporter,
        "assignee": assignee,
        "created": created.strftime("%Y-%m-%d %H:%M"),
        "updated": updated.strftime("%Y-%m-%d %H:%M"),
        "sprint": sprint,
    }


def main():
    fieldnames = [
        "id", "jira_id", "issue_type", "module", "epic_link", "title", "priority",
        "status", "test_type", "preconditions", "steps", "test_data", "expected",
        "tags", "reporter", "assignee", "created", "updated", "sprint",
    ]

    seen_titles_per_module = {}
    rows = []
    jira_num = KEY_START
    for idx in range(1, TOTAL_ROWS + 1):
        row = build_row(idx, jira_num)
        jira_num += 1
        rows.append(row)

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
