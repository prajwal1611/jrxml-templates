#!/bin/bash
echo "=========================================="
echo "  FINAL VALIDATION TEST"
echo "=========================================="
echo ""
echo "Testing: new sanction-letter-secured-unsecured_updated.jrxml"
echo ""

# Run Java validator
cd /projects/sandbox
java JRXMLValidator "jrxml-templates/new sanction-letter-secured-unsecured_updated.jrxml"

echo ""
echo "=========================================="
echo "  FOOTER CONTENT VERIFICATION"
echo "=========================================="
echo ""

# Check footer content
cd jrxml-templates
if grep -q "Page.*PAGE_NUMBER" "new sanction-letter-secured-unsecured_updated.jrxml"; then
    echo "✅ Page numbering found"
else
    echo "❌ Page numbering missing"
fi

if grep -q "Version 2.0.0" "new sanction-letter-secured-unsecured_updated.jrxml"; then
    echo "✅ Version information found"
else
    echo "❌ Version information missing"
fi

if grep -q "<pageFooter>" "new sanction-letter-secured-unsecured_updated.jrxml"; then
    echo "✅ Footer section exists"
else
    echo "❌ Footer section missing"
fi

echo ""
echo "=========================================="
echo "  ALL CHECKS COMPLETE"
echo "=========================================="
