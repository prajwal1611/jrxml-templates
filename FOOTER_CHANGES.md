# Page Footer Changes - Sanction Letter

## Summary
Added a page footer with page numbers and version information to `sanction-letter-secured-unsecured.jrxml`.

## Changes Made

### 1. Updated Bottom Margin
**File:** `sanction-letter-secured-unsecured.jrxml`
- **Changed:** `bottomMargin="40"` → `bottomMargin="60"`
- **Reason:** Increased bottom margin from 40 to 60 points to accommodate the 50-point footer height and prevent the "page height overflow" error

### 2. Added Page Footer Section
Added a new `<pageFooter>` section with the following elements:

#### Page Numbers (Left Side)
- **Position:** x=3, y=20
- **Display:** "Page X of Y" format
- Uses `$V{PAGE_NUMBER}` variable for current page
- Uses `evaluationTime="Report"` for total pages

#### Version Information (Right Side)
- **Position:** x=392, y=30 (right-aligned)
- **Display:** "Version 2.0.0"
- Static text element

## Layout Details

### Page Dimensions
- **Page Width:** 595 points (A4 width)
- **Page Height:** 842 points (A4 height)
- **Column Width:** 495 points (after margins)
- **Top Margin:** 40 points
- **Bottom Margin:** 60 points (updated)
- **Left/Right Margins:** 50 points each

### Footer Specifications
- **Footer Height:** 50 points
- **Font:** SansSerif, size 9
- **Vertical Alignment:** Middle
- **Page Number Position:** y=20 (starts 20 points from footer top)
- **Version Position:** y=30 (starts 30 points from footer top)

## Testing
To test the changes:
1. Open the JRXML file in JasperSoft Studio
2. Preview the report with sample data
3. Verify that:
   - Page numbers appear correctly on each page (e.g., "Page 1 of 3")
   - Version "2.0.0" appears on the right side of each page
   - No page height overflow errors occur
   - Footer appears on all pages consistently

## Notes
- The footer uses the standard JasperReports variables (`$V{PAGE_NUMBER}`)
- Font size reduced to 9pt to ensure readability without taking too much space
- Right-aligned version text positioned at x=392 to align with the right edge of the content area (495 - 100 width = 395, adjusted to 392 for better alignment)
