# Use unprivileged nginx — runs as non-root (uid 101) on port 8080
FROM nginxinc/nginx-unprivileged:alpine

# Copy static HTML files
COPY static/ /usr/share/nginx/html/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port (unprivileged nginx uses 8080)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
