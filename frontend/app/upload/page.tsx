import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { DatasetUploader } from "@/components/dataset-uploader";

export default function UploadPage() {
  return <main className="mx-auto max-w-6xl px-6 py-12"><DatasetUploader /><div className="mt-6 flex justify-end"><Link href="/investigations/new" className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">Continue to investigation <ArrowRight size={16} /></Link></div></main>;
}
