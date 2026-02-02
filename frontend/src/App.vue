<script setup>
import { useUserStore } from './stores/user'

const userStore = useUserStore()
</script>

<template>
  <router-view />
  <div class="footer-records">
    <a href="https://beian.mps.gov.cn/#/query/webSearch?code=33021202003929" target="_blank" rel="noopener noreferrer" class="footer-link">
      <img alt="浙公网安备图标" loading="lazy" width="16" height="16" src="/beian.png">浙公网安备33021202003929号
    </a>
    <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" class="footer-link">浙ICP备2024118372号-1</a>
    <br/>
    <p>
      By <a class="footer-link" href="https://github.com/Gentle-Lijie">Gentle-Lijie</a> for the <a href="https://github.com/unnc-aim" class="footer-link">University of Nottingham Ningbo China(UNNC) Robomaster AIM Team.</a>
    </p>
  </div>
</template>

<style>
#app {
  width: 100%;
  min-height: 100vh;
}

.footer-records {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.95);
  font-size: 12px;
  color: #999;
  z-index: 999;
}

.footer-records .footer-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #999;
  text-decoration: none;
}

.footer-records .footer-link:hover {
  color: #409eff;
}
</style>
