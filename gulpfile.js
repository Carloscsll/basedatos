const gulp = require('gulp');
const sass = require('gulp-sass')(require('sass'));
const autoprefixer = require('gulp-autoprefixer');
const cleanCSS = require('gulp-clean-css');

function styles() {
  return gulp.src('static/styles.scss')
    .pipe(sass().on('error', sass.logError))
    .pipe(autoprefixer())
    .pipe(cleanCSS())
    .pipe(gulp.dest('static/'));
}

function watch() {
  gulp.watch('static/styles.scss', styles);
}

exports.styles = styles;
exports.watch = watch;
exports.build = styles;