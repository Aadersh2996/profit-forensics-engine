# Deploy the Next.js frontend to Vercel

Deploy this only after the Railway backend is healthy and has a generated public domain. The frontend is a standard Next.js project in `frontend/` and proxies browser `/api/*` requests to the Railway URL during the Vercel build.

## Create the Vercel project

1. Sign in to Vercel and select **Add New…** → **Project**.
2. Import the GitHub repository that contains this project.
3. In **Configure Project**, set **Root Directory** to `frontend` and confirm the framework is detected as **Next.js**.
4. Keep the default build command (`npm run build`) and output settings. Do not set a custom output directory.

## Add the backend URL

1. Expand **Environment Variables**.
2. Add the name `NEXT_PUBLIC_API_URL`.
3. Set its value to the Railway domain from the backend guide, for example `https://profit-forensics-production.up.railway.app`. Do not include a trailing slash.
4. Apply it to **Production**, **Preview**, and **Development** if each environment should call the same backend; otherwise use the corresponding backend URL for each environment.
5. Select **Deploy**.

`NEXT_PUBLIC_API_URL` is intentionally public because it contains only the backend base URL. Do not add `OPENAI_API_KEY`, Razorpay key secrets, or webhook secrets to Vercel.

## Verify the public application

1. When the deployment completes, open the URL Vercel provides: `https://<project>.vercel.app`.
2. Select **Run demo dataset**, wait for all six source files to upload, and create an investigation.
3. Open the API link in the navigation. It should load the backend documentation through the frontend's `/api/docs` rewrite.
4. If the demo upload fails, open `https://<project>.up.railway.app/health` directly. If health is good, confirm the Vercel variable exactly matches that base URL and redeploy after correcting it.

## Redeploy after a backend URL change

The Next.js rewrite is produced at build time. If Railway generates a different domain or you switch environments:

1. Go to Vercel **Settings** → **Environment Variables**.
2. Update `NEXT_PUBLIC_API_URL`.
3. Open **Deployments**, select the latest deployment menu, and choose **Redeploy**.

The UI remains same-origin in the browser, so no additional CORS configuration is required for the Vercel-to-Railway integration.
