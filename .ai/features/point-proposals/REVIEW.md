---
feature: point-proposals
status: APPROVED
reviewed: 2026-11-08
head: 76f421716afcf271940eb450d672824f3bb34f8d
---

# Review — point-proposals

**Scope**: 2 files changed since review `b02a8412` (360 untracked annotation data files listed by the delta left out as unrelated data; 1 workflow artifact under `.ai/` excluded)
**Findings**: 0 must-fix · 0 should-fix · 0 nit

## Findings

### F-1 · must-fix · bug · click near another point changes the selection   [ADDRESSED]
**File**: `dataset_tools/annotate/static/index.html:243-273`
**Issue**: While a point is selected, every other marker still catches the pointer, so a click within 11 pixels of a marker selects that marker instead of moving the selected point.
**Change**: Make markers ignore the pointer while a point is selected, by adding `movable` only when `state.selectedPoint === null`, keep the selected marker's highlight, and add a page test that selects a point and clicks on top of another marker.
**Why**: REQ-5 and its edge case say the list reaches overlapping points; on small saxophones the points sit within one marker's width, so the correction the list exists for cannot be made.
**Evidence**: In Chrome, selecting point 1 from the list and clicking on marker 4 left point 1 in place and selected point 4.

### F-2 · nit · bug · pending counts stay stale after an unreadable image   [ADDRESSED]
**File**: `dataset_tools/annotate/static/index.html:548-554`
**Issue**: The error handler changes the image status without redrawing progress, so "Da fare" keeps counting an unreadable image as pending until another image updates it.
**Change**: Call `renderProgress()` after `updateRow` in the handler, as `store` does at line 441.

### F-3 · nit · bug · saved-image message shown without saved points   [ADDRESSED]
**File**: `dataset_tools/annotate/static/index.html:364-365`
**Issue**: If another tab rejected the image, the reopened image has no points and opens for clicking, yet the message says to move the points and confirm.
**Change**: Set that message only when `state.reviewPoints` holds points.
