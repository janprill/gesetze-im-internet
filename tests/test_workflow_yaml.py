import pathlib
import pytest

WORKFLOW_PATH = pathlib.Path(__file__).parent.parent / ".github" / "workflows" / "scrape.yml"


@pytest.fixture(scope="module")
def workflow_text():
    return WORKFLOW_PATH.read_text()


def test_cron_trigger(workflow_text):
    assert "0 4 * * *" in workflow_text


def test_permissions_write(workflow_text):
    assert "contents: write" in workflow_text


def test_no_ssh_keys(workflow_text):
    assert "ssh-key" not in workflow_text
    assert "deploy_key" not in workflow_text


def test_concurrency_not_cancelled(workflow_text):
    assert "cancel-in-progress: false" in workflow_text


def test_workflow_dispatch_present(workflow_text):
    assert "workflow_dispatch" in workflow_text


def test_data_branch_checkout(workflow_text):
    assert "ref: data" in workflow_text
    assert "path: data-branch" in workflow_text
