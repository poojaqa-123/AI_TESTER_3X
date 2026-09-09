# QA Onboarding Guide

## Environment setup

New QA engineers should install the Selenium framework and Playwright framework
from the internal GitHub repos, and request access to Jenkins and JIRA.

## Test case conventions

All test cases must include Preconditions, numbered Steps, Test Data, and an
Expected Result. Priority is one of Low/Medium/High and must map to a JIRA
epic link.

## Escalation process

If a test fails in CI, check the Jenkins build log first. If the root cause is
unclear, tag the module owner in the failure's JIRA ticket before escalating
further.
