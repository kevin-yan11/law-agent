import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Search,
  Users,
  FileText,
  CheckSquare,
  ArrowRight,
  Shield,
  Clock,
  MapPin,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navigation */}
      <nav className="fixed top-4 left-4 right-4 z-50 bg-white/80 backdrop-blur-md border border-slate-200 rounded-2xl shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Image src="/logo.svg" alt="AusLaw AI" width={72} height={72} />
            <span className="text-xl font-semibold text-slate-900 tracking-tight">
              AusLaw AI
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="#features"
              className="text-sm text-slate-600 hover:text-slate-900 transition-colors hidden sm:block"
            >
              Features
            </Link>
            <Link
              href="#how-it-works"
              className="text-sm text-slate-600 hover:text-slate-900 transition-colors hidden sm:block"
            >
              How it works
            </Link>
            <Link href="/login">
              <Button className="bg-sky-700 hover:bg-sky-800 text-white cursor-pointer">
                Start Free
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-sky-50 border border-sky-200 rounded-full px-4 py-1.5 mb-6">
            <MapPin className="h-4 w-4 text-sky-700" />
            <span className="text-sm text-sky-800 font-medium">
              Australian Legal Information
            </span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold text-slate-900 tracking-tight leading-tight mb-6">
            Understand Australian Law
            <br />
            <span className="text-sky-700">Without the Confusion</span>
          </h1>

          <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed">
            Get instant answers about your legal rights, find qualified lawyers,
            and receive step-by-step guidance for legal procedures across all
            Australian states and territories.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/login">
              <Button
                size="lg"
                className="bg-sky-700 hover:bg-sky-800 text-white text-lg px-8 py-6 cursor-pointer"
              >
                Ask Your Legal Question
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link href="#features">
              <Button
                variant="outline"
                size="lg"
                className="text-lg px-8 py-6 border-slate-300 text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                See How It Works
              </Button>
            </Link>
          </div>

          {/* Trust Indicators */}
          <div className="flex flex-wrap items-center justify-center gap-8 mt-14 pt-10 border-t border-slate-200">
            <div className="flex items-center gap-2 text-slate-500">
              <Shield className="h-5 w-5" />
              <span className="text-sm font-medium">Secure & Private</span>
            </div>
            <div className="flex items-center gap-2 text-slate-500">
              <Clock className="h-5 w-5" />
              <span className="text-sm font-medium">Instant Responses</span>
            </div>
            <div className="flex items-center gap-2 text-slate-500">
              <MapPin className="h-5 w-5" />
              <span className="text-sm font-medium">All Australian States</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight mb-4">
              Everything You Need to Navigate Australian Law
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Powered by AI and backed by real Australian legislation, our tools
              help you understand your rights and take action.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <FeatureCard
              icon={<Search className="h-6 w-6" />}
              title="Legal Information Lookup"
              description="Search through Australian legislation and get plain-English explanations of laws relevant to your situation. Covers Federal, NSW, and QLD law."
            />
            <FeatureCard
              icon={<Users className="h-6 w-6" />}
              title="Find a Lawyer"
              description="Get matched with qualified lawyers based on your location, legal issue, and budget. Compare rates and specializations."
            />
            <FeatureCard
              icon={<FileText className="h-6 w-6" />}
              title="Document Analysis"
              description="Upload your lease, contract, or legal document for AI-powered analysis. Understand key terms, risks, and your obligations."
            />
            <FeatureCard
              icon={<CheckSquare className="h-6 w-6" />}
              title="Step-by-Step Checklists"
              description="Get customized action plans for common legal procedures like bond disputes, small claims, or visa applications."
            />
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20 px-6 bg-slate-50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight mb-4">
              How It Works
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Get legal guidance in three simple steps
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <StepCard
              number="1"
              title="Select Your State"
              description="Choose your Australian state or territory so we can provide jurisdiction-specific information."
            />
            <StepCard
              number="2"
              title="Ask Your Question"
              description="Type your legal question in plain English. Upload documents if you need them analyzed."
            />
            <StepCard
              number="3"
              title="Get Actionable Guidance"
              description="Receive clear explanations, relevant legislation, checklists, and lawyer recommendations."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6 bg-slate-900">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight mb-4">
            Ready to Understand Your Legal Rights?
          </h2>
          <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
            Join thousands of Australians who use AusLaw AI to navigate legal
            questions with confidence.
          </p>
          <Link href="/login">
            <Button
              size="lg"
              className="bg-sky-600 hover:bg-sky-700 text-white text-lg px-8 py-6 cursor-pointer"
            >
              Start Your Free Consultation
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 bg-slate-950">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Image src="/logo.svg" alt="AusLaw AI" width={56} height={56} className="opacity-50" />
              <span className="text-slate-500 font-medium">AusLaw AI</span>
            </div>
            <p className="text-sm text-slate-500 text-center">
              This tool provides general legal information, not legal advice.
              Always consult a qualified lawyer for advice specific to your situation.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Card className="border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-200 cursor-pointer">
      <CardHeader>
        <div className="w-12 h-12 bg-sky-50 rounded-xl flex items-center justify-center text-sky-700 mb-3">
          {icon}
        </div>
        <CardTitle className="text-xl font-semibold text-slate-900">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <CardDescription className="text-base text-slate-600 leading-relaxed">
          {description}
        </CardDescription>
      </CardContent>
    </Card>
  );
}

function StepCard({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center">
      <div className="w-14 h-14 bg-sky-700 text-white rounded-full flex items-center justify-center text-2xl font-semibold mx-auto mb-5">
        {number}
      </div>
      <h3 className="text-xl font-semibold text-slate-900 mb-3">{title}</h3>
      <p className="text-slate-600 leading-relaxed">{description}</p>
    </div>
  );
}
