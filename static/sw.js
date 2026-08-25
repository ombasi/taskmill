self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function (e) {
  /* network-first; keep shell light */
});

self.addEventListener('push', function (event) {
  var data = { title: 'Taskmill', body: '', url: '/', icon: '/static/img/taskmill-logo.png' };
  try {
    if (event.data) {
      var parsed = event.data.json();
      data = Object.assign(data, parsed);
    }
  } catch (err) {
    try {
      data.body = event.data ? event.data.text() : '';
    } catch (e2) {}
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Taskmill', {
      body: data.body || '',
      icon: data.icon || '/static/img/taskmill-logo.png',
      badge: data.badge || '/static/img/taskmill-logo.png',
      data: { url: data.url || '/' },
      vibrate: [80, 40, 80],
      renotify: true,
      tag: data.tag || 'taskmill-' + Date.now(),
    })
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        var c = list[i];
        if (c.url && 'focus' in c) {
          c.navigate(url);
          return c.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
