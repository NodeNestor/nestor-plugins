#!/bin/bash
# Create a realistic test project for live Claude Code testing
set -eu

PROJECT="/workspace/test-project"
rm -rf "$PROJECT"
mkdir -p "$PROJECT/src/components" "$PROJECT/src/utils" "$PROJECT/__tests__" "$PROJECT/.claude/workflows"
cd "$PROJECT"

# Init git
git init
git config user.email "test@nodenestor.dev"
git config user.name "NodeNestor Test"

# package.json
cat > package.json << 'PKGJSON'
{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "test": "echo 'All 5 tests passed' && exit 0",
    "lint": "echo 'No lint errors' && exit 0",
    "build": "echo 'Build successful' && exit 0"
  }
}
PKGJSON

# Components (PascalCase naming convention)
for comp in UserCard ProfileView NavBar SidePanel Footer Header Modal Button Input Select Dropdown Tooltip Badge Alert Toast Spinner Avatar Card Table Form; do
cat > "src/components/${comp}.tsx" << EOF
import React from "react";

interface ${comp}Props {
  className?: string;
}

export function ${comp}({ className }: ${comp}Props) {
  return <div className={className}>${comp}</div>;
}
EOF
done

# Utils (camelCase naming convention)
cat > src/utils/formatDate.ts << 'EOF'
export function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}
EOF

cat > src/utils/validateEmail.ts << 'EOF'
export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
EOF

# A test file
cat > __tests__/UserCard.test.tsx << 'EOF'
import { UserCard } from "../src/components/UserCard";

test("UserCard renders", () => {
  expect(true).toBe(true);
});
EOF

# A buggy file to fix
cat > src/utils/buggyCalc.ts << 'EOF'
// BUG: This function has an off-by-one error
export function sumRange(start: number, end: number): number {
  let sum = 0;
  for (let i = start; i < end; i++) {  // should be <= end
    sum += i;
  }
  return sum;
}

// BUG: Doesn't handle empty arrays
export function average(numbers: number[]): number {
  const sum = numbers.reduce((a, b) => a + b, 0);
  return sum / numbers.length;  // division by zero if empty
}
EOF

# A workflow
cat > .claude/workflows/on-edit-test.yml << 'EOF'
name: run-tests-on-edit
description: Run tests after file edits
trigger:
  event: PostToolUse
  matcher: Edit
steps:
  - name: run-tests
    run: npm test
    timeout: 30
EOF

# CLAUDE.md
cat > CLAUDE.md << 'EOF'
# Test Project

This is a React/TypeScript project for testing NodeNestor plugins.

## Conventions
- Components in src/components/ use PascalCase
- Utils in src/utils/ use camelCase
- Tests in __tests__/
- Named exports only, no default exports
EOF

# Initial commit
git add -A
git commit -m "Initial commit: test project with components, utils, and bugs"

echo "Test project ready at $PROJECT"
