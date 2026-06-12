# Key user journeys for zkm-scan. The only user-facing surface is the core CLI
# (`zkm convert scan`) — not automatable headlessly from this repo, so these
# scenarios are a @manual human checklist. Run against a throwaway store
# (ZKM_STORE=/tmp/kb zkm init) with tesseract + poppler installed.

@manual
Feature: OCR scanned documents into the knowledge store

  Background:
    Given an initialized zkm store
    And the zkm-scan plugin is discoverable ("zkm plugin list" shows "scan")
    And tesseract with the configured language packs and poppler are installed

  Scenario: Import a scanned letter from a source directory
    Given zkm-config.yaml has scan.source_dir pointing at a folder with a scanned-only PDF
    When I run "zkm convert scan"
    Then a markdown file appears under scans/YYYY/MM/ named <date>_<slug>.md
    And its body contains the OCR'd text with one "<!-- page N -->" marker per non-blank page
    And the original bytes live under originals/scans/_objects/ with an inbox/scans/ symlink
    And the store has a new auto-commit
    And "zkm search" finds words from the scanned letter

  Scenario: Mail attachment deposited by zkm-eml is picked up
    Given zkm-eml has deposited a scanned image attachment into inbox/
    When I run "zkm convert scan"
    Then a scans/ markdown is created for the attachment
    And the CAS sidecar lists both the "eml" and "scan" producers

  Scenario: Text PDF is left for zkm-pdf (roadmap id:6913, after implementation)
    Given a PDF with a real text layer in scan.source_dir
    When I run "zkm convert scan"
    Then no scans/ markdown is created for it
    And .zkm-state/zkm-scan-skipped.jsonl gains an entry with reason "text-layer"
    And running "zkm convert pdf" ingests the same PDF under pdfs/

  Scenario: Re-run is a cheap no-op
    Given a previous successful "zkm convert scan" run
    When I run "zkm convert scan" again with unchanged config
    Then no new markdown files are created
    And no OCR work is re-done for previously skipped blank pages (roadmap id:8810)

  Scenario: Missing language pack fails with a clear message (roadmap id:5c02)
    Given zkm-config.yaml sets scan.lang to "deu+eng" and the deu pack is not installed
    When I run "zkm convert scan"
    Then the command fails with a message naming "deu" and how to fix it
    And no partial markdown files are left behind
