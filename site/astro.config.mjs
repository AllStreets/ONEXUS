import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://allstreets.github.io',
  base: '/ONEXUS',
  integrations: [
    starlight({
      title: 'ONEXUS',
      description: 'Open-Source Neural Executive for Unified Superintelligence',
      customCss: ['./src/styles/custom.css'],
      favicon: '/favicon.svg',
      head: [
        {
          tag: 'link',
          attrs: {
            rel: 'preconnect',
            href: 'https://fonts.googleapis.com',
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'preconnect',
            href: 'https://fonts.gstatic.com',
            crossorigin: true,
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'stylesheet',
            href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap',
          },
        },
      ],
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/AllStreets/ONEXUS' },
      ],
      sidebar: [
        {
          label: 'Setup',
          items: [
            { label: 'Installation', slug: 'getting-started/installation' },
            { label: 'Quickstart', slug: 'getting-started/quickstart' },
            { label: 'Configuration', slug: 'getting-started/configuration' },
          ],
        },
        {
          label: 'Architecture',
          items: [
            { label: 'Overview', slug: 'architecture/overview' },
            { label: 'Kernel', slug: 'architecture/kernel' },
            { label: 'Modules', slug: 'architecture/modules' },
          ],
        },
        {
          label: 'Concepts',
          items: [
            { label: 'Earned Autonomy', slug: 'concepts/earned-autonomy' },
            { label: 'Memory Tiers', slug: 'concepts/memory-tiers' },
            { label: 'Audit Trail', slug: 'concepts/audit-trail' },
            { label: 'Design Philosophy', slug: 'concepts/design-philosophy' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Build a Module', slug: 'guides/building-a-module' },
            { label: 'Connecting an LLM', slug: 'guides/connecting-an-llm' },
            { label: 'Running Tests', slug: 'guides/running-tests' },
            { label: 'Troubleshooting', slug: 'guides/troubleshooting' },
          ],
        },
        {
          label: 'Reference',
          collapsed: true,
          items: [
            { label: 'Routing Table', slug: 'reference/routing' },
            {
              label: 'Kernel',
              autogenerate: { directory: 'reference/kernel' },
            },
            {
              label: 'Modules',
              autogenerate: { directory: 'reference/modules' },
            },
          ],
        },
      ],
    }),
  ],
});
