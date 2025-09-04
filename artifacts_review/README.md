# Artifacts Review Directory

This directory contains **review artifacts only**. These are the ONLY files that should be committed to version control for submission and review.

## 📋 Submission Rules

### ✅ ALLOWED: Commit Only These Files
- `artifacts_review/**` - All files in this directory
- `generation_summary.md` - Generation statistics and configuration
- `quality_review_report.md` - Quality metrics and analysis
- `samples/*.json` - Representative samples for each task type
- `00_env_probe.md` - Environment and provider probe results

### ❌ FORBIDDEN: Never Commit These
- `data/gen/**` - Generated data files
- `runs/**` - Temporary run files and partials
- `reports/**` - Internal reports and provenance data
- `.env` - Environment variables (contains API keys)
- Any other generated or temporary files

## 📊 Generated Files

### generation_summary.md
Contains:
- Generation configuration (timeouts, concurrency, token limits)
- Provider chains used
- Success/failure statistics per task
- File paths for generated data

### quality_review_report.md
Contains:
- Schema compliance metrics
- ASK rate analysis (ALC only)
- CoT leak detection
- Diversity metrics (Distinct-2 for ALC)
- Overall quality assessment

### samples/*.json
Contains:
- `ALC_sample.json` - Representative ALC task sample
- `AR_sample.json` - Representative AR task sample
- `RSD_sample.json` - Representative RSD task sample

Each sample includes:
- Full conversation turns
- Labels and metadata
- Reasoning and source information

## 🔄 Workflow

1. **Owner Run**: Execute generation in Colab/Jupyter (not CLI)
2. **Review**: Check artifacts_review/ files for quality assessment
3. **Submit**: Commit ONLY artifacts_review/** for PR submission
4. **Clean**: Remove data/gen/, runs/, reports/ before submission

## ⚠️ Important Notes

- **Owner-Only Execution**: Long-running tasks must be executed by repository owners only
- **No CLI Generation**: Do not run generation via command line - use notebooks or colab_entry.py
- **Security**: Never commit API keys or sensitive environment variables
- **Clean Submissions**: PRs should contain only review artifacts, not raw generated data

## 📁 Directory Structure

```
artifacts_review/
├── README.md                    # This file
├── generation_summary.md       # Generation statistics
├── quality_review_report.md    # Quality analysis
├── samples/
│   ├── ALC_sample.json         # ALC representative sample
│   ├── AR_sample.json          # AR representative sample
│   └── RSD_sample.json         # RSD representative sample
└── 00_env_probe.md            # Environment probe results
```

## 🔍 Quality Gates

Before submission, ensure:
- ✅ All required files are present
- ✅ Quality metrics meet thresholds
- ✅ No sensitive data is included
- ✅ File sizes are reasonable for review
- ✅ Schema compliance is >95% for all tasks