import {
  Activity,
  Bug,
  Code2,
  FileText,
  ShieldCheck,
  TestTube2,
} from "lucide-react";

export const dashboardMetrics = [
  {
    title: "Quality Score",
    value: "91/100",
    subtitle: "Maintainability and structure",
    trend: "+12%",
    icon: Activity,
  },
  {
    title: "Test Coverage",
    value: "87%",
    subtitle: "Estimated coverage level",
    trend: "+9%",
    icon: TestTube2,
  },
  {
    title: "Security Score",
    value: "96/100",
    subtitle: "Static security checks",
    trend: "+6%",
    icon: ShieldCheck,
  },
  {
    title: "Generated Tests",
    value: "42",
    subtitle: "AI suggested test cases",
    trend: "+18",
    icon: Code2,
  },
];

export const recentProjects = [
  {
    name: "sample-fastapi-app",
    language: "Python",
    status: "Completed",
    quality: 91,
    issues: 3,
  },
  {
    name: "student-management-api",
    language: "Python",
    status: "Running",
    quality: 76,
    issues: 8,
  },
  {
    name: "booking-service",
    language: "Python",
    status: "Completed",
    quality: 84,
    issues: 5,
  },
];

export const reportHighlights = [
  {
    title: "Security issues detected",
    value: "3",
    icon: Bug,
  },
  {
    title: "PDF reports generated",
    value: "12",
    icon: FileText,
  },
];