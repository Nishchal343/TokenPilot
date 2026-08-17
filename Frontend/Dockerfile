FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# node-pty belongs to the Electron desktop target and has no Alpine prebuild;
# the browser bundle never imports it, so skip lifecycle scripts. Tailwind's
# PostCSS pipeline does need lightningcss, whose Alpine optional package is
# installed explicitly because npm can otherwise omit it in cross-platform
# lockfile installs.
RUN npm ci --ignore-scripts \
    && npm install --no-save --ignore-scripts lightningcss-linux-x64-musl@1.32.0
COPY . .
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
EXPOSE 443
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
